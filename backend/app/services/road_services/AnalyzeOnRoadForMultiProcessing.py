from multiprocessing import Process, Manager, freeze_support
import os
from .AnalyzeOnRoad import AnalyzeOnRoad
from ...core.config import settings_metric_transport
from ...utils.transport_utils import convert_frame_to_byte, log
import signal
import sys
import atexit

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

""" On Windows, Python multiprocessing uses spawn method instead of fork (like on Linux/macOS)
When spawning, Python must re-import the entire module to create a new process
When importing a module, all code at module level will be executed again"""

""" On Windows, Python multiprocessing uses spawn method instead of fork (like on Linux/macOS)
When spawning, Python must re-import the entire module to create a new process
When importing a module, all code at module level will be executed again"""

# Don't place outside Class because each time a child process is created it will be created again. Putting it in the class only initializes it once
# Class variables will also be initialized so avoid placing shared_data variables at class level
class AnalyzeOnRoadForMultiprocessing():
    """
    Attributes:
        manager (Manager()): Object for creating Lock() and other shared data types
        for processes to use together
        shared_data (Manager().dict()): Dict managing Lock and other shared data types
        for processes to use together more tightly
        processes (list): Child processes currently running
    """
    def __init__(self, regions = settings_metric_transport.REGIONS, path_videos = settings_metric_transport.PATH_VIDEOS,
        meter_per_pixels = settings_metric_transport.METER_PER_PIXELS, show_log = False, show = False, is_join_processes = False):
        """When integrating into API design, due to infinite event loop mechanism,
        there is no need to join processes to avoid being killed.
        Therefore, is_join_processes should be set to False, otherwise it will block
        the API event loop causing server congestion.
        
        Join keeps child processes finishing their work and prevents them from being killed when main ends.
        Statements after join will not execute if child processes haven't finished.
        When running as a normal script, you should join, but when integrating API, you shouldn't join
        to avoid blocking the API event loop.
        
        Args:
            path_videos (list, optional): Path to videos.
            Defaults to [ "./video_test/Van Quan.mp4", "./video_test/Van Phu.mp4", "./video_test/Nguyen Trai.mp4", "./video_test/Nga Tu So.mp4", "./video_test/Duong Lang.mp4", ].
            meter_per_pixels (list, optional): list of meter/pixel ratios.
            Defaults to [0.03, 0.09, 0.4, 0.11, 0.06].
            show_log (bool, optional): display log or not. Defaults to False.
            show (bool, optional): display video using cv2 or not. Defaults to False.
            is_join_processes (bool, optional): join child processes (should turn off when integrating api).
            Defaults to True.
        """
        self.path_videos = path_videos
        self.meter_per_pixels = meter_per_pixels
        self.regions = regions
        self.manager = Manager()
        self.shared_data = self.manager.dict()  # Used to store shared information between processes
        self.show_log = show_log
        self.show = show
        self.processes = []
        self.names = []
        self.is_join_processes = is_join_processes
        
        # Register signal handler to handle Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Register cleanup on exit
        atexit.register(self.cleanup_processes)

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C and SIGTERM signals"""
        print(f"\nReceived signal {signum}, stopping processes...")
        self.cleanup_processes()
        sys.exit(0)

    def cleanup_processes(self):
        """Stop all processes safely"""
        if hasattr(self, 'processes'):
            for p in self.processes:
                if p.is_alive():
                    print(f"Terminating process {p.pid}...")
                    p.terminate()
                    p.join(timeout=5)  # Wait up to 5 seconds
                    if p.is_alive():
                        print(f"Force killing process {p.pid}...")
                        p.kill()
            print("All processes stopped.")

    # Normal function placed here to organize code. Can be called through class or instance,
    # but cannot directly access class or instance attributes unless passed in.
    @staticmethod 
    def run_analyze_process(region, path_video, meter_per_pixel, info_dict, frame_dict, show):
        """Function running in separate process, serves as initializer for Multiprocessing.
        Set this as a static method to avoid multiprocessing errors.
        Multiprocessing will pickle variables related to the function to transfer data to child processes.
        In particular, self contains YOLO tools and other variables that cannot be pickled.
        Therefore, YOLO-related objects are initialized in this initializer function.
        When calling this initializer, it will be initialized simultaneously in the child process,
        ensuring data integrity throughout the process.
        Since some attributes in self cannot be pickled, we use @staticmethod for data safety.
        Use @staticmethod to avoid pickling the entire class instance.
        Only pass necessary parameters, not the entire self.
        
        Args:
            path_video (str): Path to the video file
            meter_per_pixel (float): Ratio of 1 real-world meter to 1 pixel
            info_dict (Manager().dict()): Dict for sharing intermediate data between processes.
            By default, it's passed by reference and will be updated if child processes modify it,
            so we can easily access processing results outside but must ensure safe access.
            frame_dict (Manager().dict()): Similar to info_dict but stores byte-encoded image information.
            Since manager doesn't have a bytes type, we store it in an intermediate dict.
            show (bool): Whether to display video or not
        """
        try:
            analyzer = AnalyzeOnRoad(
                path_video=path_video,
                meter_per_pixel=meter_per_pixel,
                info_dict=info_dict,
                frame_dict=frame_dict,
                show= show, 
                region= region
            )
            analyzer.process_on_single_video()
        except Exception as e:
            print(f"Error processing {path_video}: {e}")

    def run_multiprocessing(self):
        """Function to trigger multiprocessing execution"""
        freeze_support()
        
        # Loop through to process each video with corresponding path and meter_per_pixel parameters
        for path_video, meter_per_pixel, region in zip(self.path_videos, self.meter_per_pixels, self.regions):
            name = path_video.split('/')[-1][:-4]
            self.names.append(name)
            
            # Create manager objects
            info_dict = self.manager.dict({
                "count_car": 0,
                "count_motor": 0,
                "speed_car": 0,
                "speed_motor": 0,
            })
            frame_dict = self.manager.dict({"frame": ""})
            # Store locks and data management variables in shared_data dict for easier management.
            # Data retrieval is simpler because information like locks and data are distributed into dict
            # management to help make it more robust and concurrent-safe.
            self.shared_data[name] = {
                'info': info_dict,
                'frame': frame_dict,
            }
            
            # Create process with target as static method
            p = Process(
                target=self.run_analyze_process, 
                args=(
                    region, path_video, meter_per_pixel, info_dict, frame_dict, 
                    self.show
                ), 
                # kwargs={'show': True}
            )
            self.processes.append(p)
      
        # Start all self.processes
        for p in self.processes:
            p.start()
        
        if self.show_log:
            Process(target= log, args=(self.names, self.shared_data)).start()

        if self.is_join_processes:
            self.join_process()
    
    def join_process(self):   
        """Function to join processes with timeout"""
        for p in self.processes:
            if p.is_alive():
                p.join(timeout=10)  # 10 second timeout
                if p.is_alive():
                    print(f"Process {p.pid} could not stop, force killing...")
                    p.terminate()
                    p.join(timeout=2)
                    if p.is_alive():
                        p.kill()
        print("All processes stopped.")
    
    def get_frame_road(self, road_name : str):
        data = b""
        if road_name not in self.names:
            return data
        data = convert_frame_to_byte(self.shared_data[road_name]['frame'].get('frame', b""))
        return data
    
    def get_info_road(self, road_name : str):
        if road_name not in self.names:
            return {}
        return dict(self.shared_data[road_name]['info'])

#***********************************************************Script for testing************************************************************************
if __name__ == '__main__':
    # freeze_support should be called immediately in the main block
    freeze_support()
    analyzer = AnalyzeOnRoadForMultiprocessing(
        show_log= True,
        show= True, 
        is_join_processes= True
    )
    analyzer.run_multiprocessing()
    
    # Phần main process
    # time.sleep(5)
    # while True:
    #     try:
    #         vehicles_info = analyzer.get_vehicles_info()
    #         frames = analyzer.get_frames()
            
    #         print("\nCurrent Vehicles Info:")
    #         for name, info in vehicles_info.items():
    #             print(f"{name}: {info}")
            
    #         # print("\nCurrent Frames:")
    #         for name, frame in frames.items():
    #             print(f"{name}: {frame['frame'][:10]}...")  # Print first 10 characters of the frame string
            
    #         time.sleep(0.01)
    #     except KeyboardInterrupt:
    #         print("Exiting...")
    #         break