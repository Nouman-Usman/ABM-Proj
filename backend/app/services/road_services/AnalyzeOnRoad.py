import os
from overrides import override
from .AnalyzeOnRoadBase import AnalyzeOnRoadBase
from ...core.config import settings_metric_transport
# Set this way to avoid errors from using shared AI library
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

class AnalyzeOnRoad(AnalyzeOnRoadBase):
    """This class inherits from Base class (sequential processing). This child class is not yet code for multiprocessing\
    but just a slight improvement from the base code (class Base) to be able to process input video in one process\
    while being able to access result information without data race conditions.
    """
    def __init__(self, path_video, meter_per_pixel, info_dict, frame_dict, region, model_path = settings_metric_transport.MODELS_PATH, time_step=30,
                 is_draw=True, device= settings_metric_transport.DEVICE, iou=0.3, conf=0.2, show=True):
        """This class inherits from the Base class (sequential processing). This subclass is not code for multiprocessing
        but rather a slight improvement from the base code (Base class) to be able to process input video in a separate process
        while also being able to retrieve result information without data race conditions.

        Args:
            path_video (str): Path to the video file
            meter_per_pixel (float): Ratio of 1 real-world meter to 1 pixel
            info_dict (Manager().dict()): Dict for sharing intermediate data between processes.
            By default, it's passed by reference and will be updated if child processes modify it,
            so we can easily access processing results outside but must ensure safe access.
            frame_dict (Manager().dict()): Similar to info_dict but stores encoded byte-format image information.
            Since manager() doesn't support this type, we use an intermediate dict to store the byte code in its value (key is "frame")
            model_path (str): Path to the model. Defaults to "best.pt".
            time_step (int): Time interval between 2 vehicle information updates. Defaults to 30.
            is_draw (bool): Variable specifying whether to draw processed information on the frame. Defaults to True.
            device (str): Use GPU or CPU. Defaults to 'cpu'.
            iou (float): Confidence threshold for bounding box. Defaults to 0.3.
            conf (float): Confidence threshold for predicted labels. Defaults to 0.2.
            show (bool): Display processed video via opencv, set to False when using as server to avoid wasting resources.
            Defaults to True.
            
        Examples:
        Instructions for running single video processing
        >>> analyzer = AnalyzeOnRoad(
        >>>     path_video=path_video,
        >>>     meter_per_pixel=meter_per_pixel,
        >>>     info_dict=info_dict,
        >>>     frame_dict=frame_dict,
        >>>     **kwargs
        >>> )
        >>> analyzer.process_on_single_video()
        """
        super().__init__(path_video, meter_per_pixel, model_path, time_step,
                 is_draw, device, iou, conf, show, region)
        self.info_dict = info_dict
        self.frame_dict = frame_dict

    @override
    def update_for_frame(self):
        """Update current processing frame and assign to Manager.dict() to easily share data between processes.
        """
        try: 
           self.frame_dict["frame"] = self.frame_output
        except Exception as e:
            print(f"Error updating latest frame of {self.name}: {e}")

    @override
    def update_for_vehicle(self):
        """Function to update information about current processing and assign to Manager.dict() to share with each other."""
        try:
            self.info_dict["count_car"] = self.count_car_display
            self.info_dict["count_motor"] = self.count_motor_display
            self.info_dict["speed_car"] = self.speed_car_display
            self.info_dict["speed_motor"] = self.speed_motor_display
        except Exception as e:
            print(f"Error updating vehicle information of {self.name}: {e}")

#******************************************************** Script for testing *********************************************************
if __name__ == "__main__":
    from multiprocessing import Manager
    manager = Manager()
  
    path_video = "./video_test/Lang_Street.mp4"
    meter_per_pixel = 0.04
    info_dict = manager.dict({"count_car": 0,
                             "count_motor": 0,
                             "speed_car": 0,
                             "speed_motor": 0})
    frame_dict = manager.dict({"frame": None})
    
    analyzer = AnalyzeOnRoad(
        path_video=path_video,
        meter_per_pixel=meter_per_pixel,
        info_dict=info_dict,
        frame_dict=frame_dict,
        show=True
    )
    
    analyzer.process_on_single_video()
    