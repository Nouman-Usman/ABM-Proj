from abc import abstractmethod
import cvzone
import cv2
import os
import numpy as np
from datetime import datetime
from ultralytics import solutions
from ...utils.transport_utils import *
from ...core.config import settings_metric_transport
# Add this to avoid conflicts
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

class AnalyzeOnRoadBase:
    """Wrapper class for sequential video processing with OOP encapsulation
        Attributes:
            count_car_display (int): Average number of cars
            speed_car_display (int): Average instantaneous speed of cars
            count_moto_display (int): Average number of motorcycles
            speed_moto_display (int): Average instantaneous speed of motorcycles
            speed_tool (solutions.SpeedEstimator()): YOLO SpeedEstimator object
            frame_output (np.array): Processed image with or without visualization (depends on is_draw flag)\
            Detected information
        Examples:
            Guide to process a single video
            >>> analyzer = AnalyzeOnRoadBase(
            >>>     path_video=path_video,
            >>>     meter_per_pixel=meter_per_pixel,
            >>>     info_dict=info_dict,
            >>>     frame_dict=frame_dict,
            >>>     lock_info=lock_info,
            >>>     lock_frame=lock_frame,
            >>> )
            >>> analyzer.process_on_single_video()
    """
    def __init__(self, path_video = "./video_test/Lang_Street.mp4", meter_per_pixel = 0.06,
                 model_path= settings_metric_transport.MODELS_PATH, time_step=30,
                 is_draw=True, device= settings_metric_transport.DEVICE, iou=0.3, conf=0.2, show=False,
                 region = np.array([[50, 400], [50, 265], [370, 130], [600, 130], [600, 400]])):
        """Sequential processing function with YOLO application and class-based encapsulation improvement

        Args:
            path_video (str): Path to the video file
            meter_per_pixel (float): Ratio of 1 meter in reality to 1 pixel
            model_path (str): Path to the model. Defaults to "best.pt".
            time_step (int): Time interval between vehicle information updates. Defaults to 30.
            is_draw (bool): Whether to draw processing information on frames. Defaults to True.
            device (str): Use GPU or CPU. Defaults to 'cpu'.
            iou (float): Confidence threshold for bounding boxes. Defaults to 0.3.
            conf (float): Confidence threshold for predicted labels. Defaults to 0.2.
            show (bool): Display processed video via OpenCV, set to False when integrating as server to avoid wasting resources.\
            Defaults to True.
            max_buffer_size (int): Kích thước tối đa của buffer cho deque. Defaults to 900.
        """
        self.speed_tool = solutions.SpeedEstimator(
            model=model_path,
            tracker = 'bytetrack.yaml',
            verbose=False,
            show=False,
            device=device,
            iou=iou,
            conf=conf,
            meter_per_pixel=meter_per_pixel,
            max_hist=20
        )

        self.region = region
        self.region_pts = region.reshape((-1, 1, 2))
        # Bounding box (x, y, w, h) for fast pre-filtering before polygon test
        self.region_bbox = cv2.boundingRect(self.region_pts)

        self.show = show
        self.path_video = path_video
        self.name = path_video.split('/')[-1][:-4]

        self.count_car_display = 0
        self.list_count_car = []
        self.speed_car_display = 0
        self.list_speed_car = []

        self.count_motor_display = 0
        self.list_count_motor = []
        self.speed_motor_display = 0
        self.list_speed_motor = []

        self.time_pre = datetime.now()
        self.frame_output = None
        self.time_step = time_step
        self.frame_predict = None
        self.is_draw = is_draw
        self.delta_time = 0
        self.time_pre_for_fps = datetime.now()

        # ROI
        self.roi_y_start = 130
        self.roi_x_start = 50

        # Draw
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = 0.5
        self.font_thickness = 1
        self.color_motor = (0, 0, 255)  # Red for motorcycles
        self.color_car = (255, 0, 0)    # Blue for cars
        self.color_region = (0, 255, 255)  # Yellow for region

        # Tracking
        self.ids = None
        self.speeds = {}
        self.boxes = None
        self.classes = None
        self.ids_old = set()
    @abstractmethod
    def update_for_frame(self):
        pass

    @abstractmethod
    def update_for_vehicle(self):
        pass

    def update_data(self):
        """This function will be called to update frame data and vehicle information after the configured time_step interval"""

        # Call this function to update frame data (always updated to ensure real-time performance)
        self.update_for_frame()

        # Calculate elapsed time since last update
        time_now = datetime.now()
        self.delta_time = (time_now - self.time_pre).total_seconds()

        # When enough time has passed, update vehicle information
        if self.delta_time >= self.time_step:
            self.time_pre = time_now

            # Calculate average values for the cycle (ignoring zeros)
            (
                self.count_car_display,
                self.speed_car_display,
                self.count_motor_display,
                self.speed_motor_display,
            ) = avg_none_zero_batch(
                self.list_count_car,
                self.list_speed_car,
                self.list_count_motor,
                self.list_speed_motor,
            )

            # Update vehicle information into info_dict
            self.update_for_vehicle()

            # Reset lists to prepare for next update
            self.list_count_car.clear()
            self.list_count_motor.clear()
            self.list_speed_car.clear()
            self.list_speed_motor.clear()
            self.ids_old.clear()

    def process_single_frame(self, frame_input):
        """Process a single frame
        Args:
            frame_input (np.array): Image read from OpenCV
        """
        try:
            # Avoid copying entire frame, just create a view
            self.frame_output = frame_input

            # Use direct ROI view (avoid extra copy); copy is performed when passed to speed_tool
            self.frame_predict = self.frame_output[self.roi_y_start:, self.roi_x_start:]

            # Need to use copy to prevent tool from overwriting labels on input image
            self.speed_tool.process(self.frame_predict.copy())

            self.post_processing()

            # Draw information on image
            if self.is_draw:
                self.draw_info_to_frame_output()
            # p = Thread(target= lambda : self.post_processing())
            # p.start()


            # Update data
            self.update_data()

        except Exception as e:
            print(f"Error processing file {self.name}: {e}")

    def post_processing(self):
        if self.speed_tool.track_data is not None:
            # Batch convert to numpy once (reduces multiple attribute accesses)
            track_data = self.speed_tool.track_data
            speeds_dict = self.speed_tool.spd  # dict: id -> speed

            # Check that attributes are not None before calling .cpu()
            if track_data.id is None or track_data.cls is None or track_data.xyxy is None:
                return
            
            ids = track_data.id.cpu().numpy().astype(np.int32)
            classes = track_data.cls.cpu().numpy().astype(np.int32)
            boxes = track_data.xyxy.cpu().numpy().astype(np.int32)

            # Save to attributes for drawing
            self.speeds = speeds_dict
            self.ids = ids
            self.classes = classes
            self.boxes = boxes

            # Count instantaneous density
            car_mask = (classes == 0)
            motor_mask = (classes == 1)
            self.list_count_car.append(int(np.sum(car_mask)))
            self.list_count_motor.append(int(np.sum(motor_mask)))

            car_ids = ids[car_mask]
            motor_ids = ids[motor_mask]
            ids_old = self.ids_old

            def collect_speeds(new_ids: np.ndarray):
                if new_ids.size == 0:
                    return []
                if ids_old:
                    mask_new = ~np.isin(new_ids, list(ids_old), assume_unique=False)
                    new_ids = new_ids[mask_new]
                if new_ids.size == 0:
                    return []
                spd_arr = np.array([speeds_dict.get(int(i), 0.0) for i in new_ids], dtype=np.float32)
                valid_mask = spd_arr > 0.0
                if not np.any(valid_mask):
                    return []
                ids_old.update(new_ids[valid_mask].tolist())
                return spd_arr[valid_mask].tolist()

            car_speeds = collect_speeds(car_ids)
            motor_speeds = collect_speeds(motor_ids)
            if car_speeds:
                self.list_speed_car.extend(car_speeds)
            if motor_speeds:
                self.list_speed_motor.extend(motor_speeds)


    def draw_info_to_frame_output(self):
        """Draw information on image - optimized version"""
        try:
            if self.ids is not None and len(self.ids) > 0:
                # Vectorized center calculation
                x1 = self.boxes[:, 0]
                y1 = self.boxes[:, 1]
                x2 = self.boxes[:, 2]
                y2 = self.boxes[:, 3]

                cx = ((x1 + x2) // 2).astype(np.int32)
                cy = ((y1 + y2) // 2).astype(np.int32)

                # Batch ROI
                cx_adj = cx + self.roi_x_start
                cy_adj = cy + self.roi_y_start

                # Find points in ROI region: prefilter using bounding box to reduce pointPolygonTest calls
                bx, by, bw, bh = self.region_bbox
                in_bbox_mask = (
                    (cx_adj >= bx) & (cx_adj < bx + bw) &
                    (cy_adj >= by) & (cy_adj < by + bh)
                )
                candidate_idx = np.nonzero(in_bbox_mask)[0]
                valid_list = []
                region_pts_local = self.region_pts  # local ref
                for idx in candidate_idx:
                    if cv2.pointPolygonTest(region_pts_local, (int(cx_adj[idx]), int(cy_adj[idx])), False) >= 0:
                        valid_list.append(idx)
                if valid_list:
                    valid_indices = np.asarray(valid_list, dtype=np.int32)
                else:
                    valid_indices = np.empty((0,), dtype=np.int32)

                for idx in valid_indices:
                    track_id = self.ids[idx]
                    class_id = self.classes[idx]
                    speed_id = self.speeds.get(track_id, 0)

                    color = self.color_motor if class_id == 1 else self.color_car
                    label = f"{speed_id} km/h"

                    cx_local = cx[idx]
                    cy_local = cy[idx]

                    cv2.putText(self.frame_predict, label,
                               (cx_local - 50, cy_local - 15),
                               self.font, self.font_scale, color, self.font_thickness)
                    cv2.circle(self.frame_predict, (cx_local, cy_local), 5, color, -1)

            # Reattach the cropped region back to the original frame for re-prediction
            self.frame_output[self.roi_y_start:, self.roi_x_start:] = self.frame_predict
            cv2.polylines(self.frame_output, [self.region_pts],
                         isClosed=True, color=self.color_region, thickness=4)

            info = [
                f"Motorcycles: {self.count_motor_display} vehicles, Avg speed = {self.speed_motor_display} km/h",
                f"Cars: {self.count_car_display} vehicles, Avg speed = {self.speed_car_display} km/h"
            ]

            colors = [(0, 0, 200), (200, 0, 0)]

            # for i, t in enumerate(info):
            #     cvzone.putTextRect(
            #         self.frame_output, t,
            #         (10, 25 + i * 35),
            #         scale=1.5, thickness=2,
            #         colorT=colors[i],
            #         colorR=(50, 50, 50),
            #         border=2,
            #         colorB=(255, 255, 255)
            #     )

        except Exception as e:
            print(f"Error while drawing: {e}")

    def process_on_single_video(self):
        """This function will be called to process video by reading and processing each frame"""
        cam = cv2.VideoCapture(self.path_video)

        if not cam.isOpened():
            print(f'Cannot open video: {self.path_video}')
            return

        target_size = (600, 400)

        try:
            while True:
                check, cap = cam.read()

                if not check:
                    print(f'Video ended: {self.path_video}')
                    # Restart video to loop
                    cam.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

                cap = cv2.resize(cap, target_size)

                # FPS calculation - optimized
                time_now = datetime.now()
                delta_time = (time_now - self.time_pre_for_fps).total_seconds()
                fps = round(1 / delta_time) if delta_time > 0 else 0
                self.time_pre_for_fps = time_now

                cvzone.putTextRect(cap, f"FPS: {fps}",
                                 (516, 20),
                                 scale=1.1, thickness=2,
                                 colorT=(0, 255, 100),
                                 colorR=(50, 50, 50),
                                 border=2,
                                 colorB=(255, 255, 255))

                # Process each frame
                self.process_single_frame(cap)

                # Display frame if show is True
                if self.show:
                    cv2.imshow(f'{self.name}', self.frame_output)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

        except KeyboardInterrupt:
            print(f"Stopped processing {self.name}")
        except Exception as e:
            print(f"Error processing {self.name}: {e}")
        finally:
            # Release resources
            cam.release()
            if self.show:
                cv2.destroyAllWindows()

#************************************************************************ Script for testing *******************************************************
if __name__ == "__main__":
    # Example usage
    path_video = settings_metric_transport.PATH_VIDEOS[3]
    meter_per_pixel = settings_metric_transport.METER_PER_PIXELS[3]

    analyzer = AnalyzeOnRoadBase(
        path_video=path_video,
        meter_per_pixel=meter_per_pixel,
        region=settings_metric_transport.REGIONS[3],
        show=True
    )

    analyzer.process_on_single_video()