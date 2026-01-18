import numpy as np
import cv2
import time
from typing import Any, Dict
from ..core.config import get_threshold_for_road

def convert_frame_to_byte(img: np.array) -> bytes:
    """ Function to convert image from numpy format to bytes
    Args:
        img (np.array): image data read by cv2

    Returns:
        bytes: byte code
    """
    if img is not None:
        try:
            _, jpeg = cv2.imencode('.jpg', img)
            return jpeg.tobytes()
        except Exception as e:
            print(f"Error converting to bytes {e}")
            return None
    return None

def avg_none_zero(lst: list) -> int:
    non_zero = [x for x in lst if x != 0]
    return sum(non_zero) // len(non_zero) if non_zero else 0

def avg_none_zero_batch(
    car_counts: list,
    car_speeds: list,
    motor_counts: list,
    motor_speeds: list,
):
    """Calculate average ignoring 0 for 4 lists simultaneously.
    Returns tuple (count_car_avg, speed_car_avg, count_motor_avg, speed_motor_avg).
    Makes code concise and reduces overhead from repeated function calls.
    """
    # Use fast list comprehension, avoid creating unnecessary numpy array
    def _avg(lst):
        non_zero = [x for x in lst if x > 1]
        return (sum(non_zero) // len(non_zero)) if non_zero else 0

    return (
        _avg(car_counts),
        _avg(car_speeds),
        _avg(motor_counts),
        _avg(motor_speeds),
    )
    
def log(names : str, shared_data : dict) -> str:
    """Function to print log information of processing
    This function gets overall data from share_data (Manager.dict() used for inter-process communication)
    Set this function as static method because to avoid multiprocessing errors from pickling variables
    related to the function to transfer data to child process, especially self containing YOLO tools
    and other variables that cannot be pickled. Use @staticmethod to avoid pickling the entire class instance. Only
    pass necessary parameters, don't pass entire self"""
    
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    try:
        while True:
            print(f"{BOLD}{CYAN}--------------------------------------- [Log at {time.strftime('%H:%M:%S')}] --------------------------------------------{RESET}")
            print(f"{BOLD}| {'Road Name':<25} | {'Information':<70} |{RESET}")
            print(f"{'-'*102}")
            
            for name in names:
                try:
                    if name in shared_data:
                        road_data = shared_data[name]
                        info_dict = road_data['info']
                    
                        count_car = info_dict.get('count_car', 0)
                        count_motor = info_dict.get('count_motor', 0)
                        speed_car = info_dict.get('speed_car', 0)
                        speed_motor = info_dict.get('speed_motor', 0)
                    
                        info_str = f"Cars: {count_car} vehicles, Avg speed: {speed_car} km/h | Motorcycles: {count_motor} vehicles, Avg speed: {speed_motor} km/h"
                        print(f"| {YELLOW}{name:<25}{RESET} | {GREEN}{info_str:<70}{RESET} |")
                    else:
                        print(f"| {YELLOW}{name:<25}{RESET} | {GREEN}{'Initializing...':<70}{RESET} |")
                except Exception as e:
                    print(f"| {YELLOW}{name:<25}{RESET} | {GREEN}{f'Error: {str(e)}':<70}{RESET} |")
            
            print(f"{'-'*102}\n\n")
            time.sleep(5)
    except KeyboardInterrupt:
        print("Log ended.")
        
    

def enrich_info_with_thresholds(data: Dict[str, Any], road_name: str) -> Dict[str, Any]:
    """Attach density_status, speed_status and thresholds to a data dict when possible.

    This function is defensive: if expected numeric fields are missing or invalid,
    it will leave the original data intact and return it unchanged.
    """
    if not isinstance(data, dict):
        return data

    threshold = get_threshold_for_road(road_name)

    try:
        count_car = int(data.get("count_car", 0) or 0)
        count_motor = int(data.get("count_motor", 0) or 0)
        speed_car = float(data.get("speed_car", 0) or 0)
        speed_motor = float(data.get("speed_motor", 0) or 0)

        total = count_car + count_motor
        if total > threshold["c2"]:
            density_status = "Congested"
        elif total > threshold["c1"]:
            density_status = "Busy"
        else:
            density_status = "Clear"

        avg_speed = (speed_car + speed_motor) / 2 if (speed_car or speed_motor) else 0
        speed_status = "Fast" if avg_speed >= threshold["v"] else "Slow"

        # Attach computed fields
        data["density_status"] = density_status
        data["speed_status"] = speed_status
        data["thresholds"] = threshold

    except Exception:
        # If anything goes wrong, return original data without raising
        return data

    return data
