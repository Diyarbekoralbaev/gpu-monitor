import argparse
import subprocess
import platform
import os
import pynvml


def parse_arguments():
    parser = argparse.ArgumentParser(description="GPU Monitoring Tool with Alerts and Notifications")
    parser.add_argument('--temp', type=float, default=80.0,
                        help='Temperature threshold in °C (default: 80.0)')
    parser.add_argument('--util', type=float, default=90.0,
                        help='GPU utilization threshold in %% (default: 90.0)')
    parser.add_argument('--mem-util', type=float, default=90.0,
                        help='Memory utilization threshold in %% (default: 90.0)')
    parser.add_argument('--power', type=float, default=250.0,
                        help='Power draw threshold in Watts (default: 250.0)')
    parser.add_argument('--sound', action='store_true',
                        help='Enable sound alerts when thresholds are exceeded')
    parser.add_argument('--sound-file', type=str, default=None,
                        help='Path to custom sound file for alerts (WAV format)')
    return parser.parse_args()


def detect_gpu():
    try:
        nvidia_smi = subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if nvidia_smi.returncode == 0:
            return 'NVIDIA'
        else:
            return 'Unknown'
    except FileNotFoundError:
        return 'Unknown'


def get_gpu_name(index):
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(index)
        name = pynvml.nvmlDeviceGetName(handle)
        return name.decode('utf-8') if hasattr(name, 'decode') else name
    except pynvml.NVMLError:
        return "Unknown"


def get_nvidia_stats(device_count):
    stats = []
    for i in range(device_count):
        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
        stat = {'gpu_index': i}

        try:
            name = pynvml.nvmlDeviceGetName(handle)
            stat['name'] = name.decode('utf-8') if hasattr(name, 'decode') else name
        except pynvml.NVMLError:
            stat['name'] = "Unknown"

        try:
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            stat['memory_total'] = mem_info.total / (1024 ** 2)
            stat['memory_used'] = mem_info.used / (1024 ** 2)
            stat['memory_utilization'] = (mem_info.used / mem_info.total) * 100
        except pynvml.NVMLError:
            stat['memory_total'] = stat['memory_used'] = stat['memory_utilization'] = 0

        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            stat['utilization'] = util.gpu
            stat['memory_utilization_rate'] = util.memory
        except pynvml.NVMLError:
            stat['utilization'] = stat['memory_utilization_rate'] = 0

        try:
            stat['temperature'] = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except pynvml.NVMLError:
            stat['temperature'] = 0

        try:
            power_draw = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
            power_limit = pynvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000
            stat['power_draw'] = power_draw
            stat['power_limit'] = power_limit
        except pynvml.NVMLError:
            stat['power_draw'] = stat['power_limit'] = 0

        try:
            stat['fan_speed'] = pynvml.nvmlDeviceGetFanSpeed(handle)
        except pynvml.NVMLError:
            stat['fan_speed'] = 0

        try:
            stat['clock_speed'] = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
        except pynvml.NVMLError:
            stat['clock_speed'] = 0

        # Retrieve processes
        processes = []
        try:
            compute_procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            for proc in compute_procs:
                processes.append({
                    'pid': proc.pid,
                    'used_memory': proc.usedGpuMemory / (1024 ** 2),
                    'type': 'C'
                })
        except pynvml.NVMLError:
            pass

        try:
            graphics_procs = pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle)
            for proc in graphics_procs:
                processes.append({
                    'pid': proc.pid,
                    'used_memory': proc.usedGpuMemory / (1024 ** 2),
                    'type': 'G'
                })
        except pynvml.NVMLError:
            pass

        # Get process names
        for proc in processes:
            pid = proc['pid']
            proc['name'] = get_process_name(pid)

        stat['processes'] = processes
        stats.append(stat)
    return stats


def get_process_name(pid):
    try:
        if platform.system() == 'Windows':
            cmd = ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = result.stdout.strip().strip('"').split('","')
            return output[0] if output else 'Unknown'
        else:
            with open(f'/proc/{pid}/cmdline', 'r') as f:
                cmdline = f.read().replace('\x00', ' ').strip()
                return cmdline if cmdline else 'Unknown'
    except:
        return 'Unknown'
