import socket
import threading
import ipaddress
import subprocess
import platform
import re
from queue import Queue
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class ScanStatus(Enum):
    SUCCESS = "success"
    NO_INTERFACES = "no_interfaces"
    ERROR = "error"


@dataclass
class NetworkInterface:
    ip: str
    mask: str
    network: str = ""
    
    def __post_init__(self):
        try:
            net = ipaddress.IPv4Network(f"{self.ip}/{self.mask}", strict=False)
            self.network = str(net)
        except:
            self.network = f"{self.ip}/24"


@dataclass
class ScanResult:
    status: ScanStatus
    servers: List[str] = field(default_factory=list)
    scanned_networks: List[str] = field(default_factory=list)
    total_hosts_scanned: int = 0
    scan_time: float = 0.0
    error: Optional[str] = None


class NetworkScanner:
    """Сканер для поиска серверов на указанном порту"""
    
    def __init__(
        self,
        port: int = 1414,
        timeout: float = 0.5,
        max_threads: int = 100,
        on_found: Optional[Callable[[str, int], None]] = None
    ):
        """
        Args:
            port: Порт для сканирования
            timeout: Таймаут подключения в секундах
            max_threads: Максимальное количество потоков
            on_found: Callback при нахождении сервера (ip, port)
        """
        self.port = port
        self.timeout = timeout
        self.max_threads = max_threads
        self.on_found = on_found
        
        self._found_servers: List[str] = []
        self._lock = threading.Lock()
        self._hosts_scanned = 0
    
    # ==================== ПОЛУЧЕНИЕ ИНТЕРФЕЙСОВ ====================
    
    def get_all_interfaces(self) -> List[NetworkInterface]:
        """Получает все локальные сетевые интерфейсы"""
        system = platform.system().lower()
        
        if system == "windows":
            interfaces = self._get_interfaces_windows()
        else:
            interfaces = self._get_interfaces_unix()
        
        # Fallback через socket
        if not interfaces:
            interfaces = self._get_interfaces_socket()
        
        # Фильтруем только приватные IP
        return [
            iface for iface in interfaces 
            if self._is_private_ip(iface.ip)
        ]
    
    def _get_interfaces_windows(self) -> List[NetworkInterface]:
        """Получение интерфейсов на Windows"""
        interfaces = []
        
        try:
            result = subprocess.run(
                ['ipconfig', '/all'],
                capture_output=True,
                text=True,
                encoding='cp866',
                errors='ignore',
                timeout=10
            )
            
            output = result.stdout
            
            # Разбиваем на блоки адаптеров
            blocks = re.split(r'\r?\n(?=\S)', output)
            
            for block in blocks:
                # IPv4 адрес
                ip_match = re.search(
                    r'IPv4[^\d]*(\d+\.\d+\.\d+\.\d+)', 
                    block
                )
                # Маска подсети
                mask_match = re.search(
                    r'(?:Subnet Mask|Маска подсети)[^\d]*(\d+\.\d+\.\d+\.\d+)', 
                    block
                )
                
                if ip_match:
                    ip = ip_match.group(1)
                    mask = mask_match.group(1) if mask_match else '255.255.255.0'
                    interfaces.append(NetworkInterface(ip=ip, mask=mask))
                    
        except (subprocess.SubprocessError, OSError):
            pass
        
        return interfaces
    
    def _get_interfaces_unix(self) -> List[NetworkInterface]:
        """Получение интерфейсов на Linux/macOS"""
        interfaces = []
        
        # Метод 1: ip addr (современный Linux)
        try:
            result = subprocess.run(
                ['ip', 'addr'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                pattern = r'inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)'
                for ip, prefix in re.findall(pattern, result.stdout):
                    mask = self._prefix_to_mask(int(prefix))
                    interfaces.append(NetworkInterface(ip=ip, mask=mask))
                
                if interfaces:
                    return interfaces
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
        
        # Метод 2: ifconfig (macOS, старый Linux)
        try:
            result = subprocess.run(
                ['ifconfig'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # macOS формат: inet X.X.X.X netmask 0xffffff00
                # Linux формат: inet X.X.X.X netmask 255.255.255.0
                blocks = re.split(r'\n(?=\S)', result.stdout)
                
                for block in blocks:
                    ip_match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', block)
                    if ip_match:
                        ip = ip_match.group(1)
                        
                        # Ищем маску
                        hex_mask = re.search(r'netmask\s+0x([0-9a-fA-F]+)', block)
                        dec_mask = re.search(r'netmask\s+(\d+\.\d+\.\d+\.\d+)', block)
                        
                        if hex_mask:
                            mask = self._hex_to_mask(hex_mask.group(1))
                        elif dec_mask:
                            mask = dec_mask.group(1)
                        else:
                            mask = '255.255.255.0'
                        
                        interfaces.append(NetworkInterface(ip=ip, mask=mask))
                        
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
        
        return interfaces
    
    def _get_interfaces_socket(self) -> List[NetworkInterface]:
        """Fallback метод через socket"""
        interfaces = []
        
        # Метод 1: gethostbyname_ex
        try:
            hostname = socket.gethostname()
            _, _, ip_list = socket.gethostbyname_ex(hostname)
            
            for ip in ip_list:
                interfaces.append(NetworkInterface(ip=ip, mask='255.255.255.0'))
        except socket.error:
            pass
        
        # Метод 2: подключение к внешнему адресу
        for target in [('8.8.8.8', 53), ('1.1.1.1', 53), ('208.67.222.222', 53)]:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(1)
                s.connect(target)
                ip = s.getsockname()[0]
                s.close()
                
                if not any(iface.ip == ip for iface in interfaces):
                    interfaces.append(NetworkInterface(ip=ip, mask='255.255.255.0'))
            except socket.error:
                pass
        
        return interfaces
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    @staticmethod
    def _is_private_ip(ip: str) -> bool:
        """Проверяет, является ли IP приватным"""
        try:
            addr = ipaddress.IPv4Address(ip)
            return addr.is_private and not addr.is_loopback
        except (ipaddress.AddressValueError, ValueError):
            return False
    
    @staticmethod
    def _prefix_to_mask(prefix: int) -> str:
        """Конвертирует CIDR префикс в маску подсети"""
        mask_int = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
        return socket.inet_ntoa(mask_int.to_bytes(4, 'big'))
    
    @staticmethod
    def _hex_to_mask(hex_mask: str) -> str:
        """Конвертирует hex маску в обычную"""
        try:
            mask_int = int(hex_mask, 16)
            return socket.inet_ntoa(mask_int.to_bytes(4, 'big'))
        except ValueError:
            return '255.255.255.0'
    
    # ==================== СКАНИРОВАНИЕ ====================
    
    def _check_port(self, ip: str) -> bool:
        """Проверяет доступность порта на IP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, self.port))
            sock.close()
            return result == 0
        except (socket.error, OSError):
            return False
    
    def _scan_worker(self, queue: Queue) -> None:
        """Рабочий поток сканирования"""
        while True:
            try:
                ip = queue.get_nowait()
            except:
                break
            
            if self._check_port(ip):
                with self._lock:
                    self._found_servers.append(ip)
                    if self.on_found:
                        self.on_found(ip, self.port)
            
            with self._lock:
                self._hosts_scanned += 1
            
            queue.task_done()
    
    def _scan_network(self, network_str: str) -> int:
        """Сканирует одну сеть, возвращает количество хостов"""
        try:
            network = ipaddress.IPv4Network(network_str, strict=False)
            hosts = list(network.hosts())
            
            if not hosts:
                return 0
            
            queue = Queue()
            for host in hosts:
                queue.put(str(host))
            
            threads = []
            num_threads = min(self.max_threads, len(hosts))
            
            for _ in range(num_threads):
                t = threading.Thread(target=self._scan_worker, args=(queue,))
                t.daemon = True
                t.start()
                threads.append(t)
            
            queue.join()
            
            return len(hosts)
            
        except (ipaddress.AddressValueError, ValueError):
            return 0
    
    def scan_local_networks(self) -> ScanResult:
        """
        Сканирует все локальные сети
        
        Returns:
            ScanResult с найденными серверами
        """
        import time
        start_time = time.time()
        
        self._found_servers = []
        self._hosts_scanned = 0
        
        # Получаем все интерфейсы
        interfaces = self.get_all_interfaces()
        
        if not interfaces:
            return ScanResult(
                status=ScanStatus.NO_INTERFACES,
                error="No network interfaces found"
            )
        
        # Убираем дублирующиеся сети
        unique_networks = list(set(iface.network for iface in interfaces))
        
        try:
            for network in unique_networks:
                self._scan_network(network)
            
            # Убираем дубликаты серверов
            unique_servers = list(set(self._found_servers))
            
            return ScanResult(
                status=ScanStatus.SUCCESS,
                servers=sorted(unique_servers),
                scanned_networks=unique_networks,
                total_hosts_scanned=self._hosts_scanned,
                scan_time=time.time() - start_time
            )
            
        except Exception as e:
            return ScanResult(
                status=ScanStatus.ERROR,
                servers=list(set(self._found_servers)),
                scanned_networks=unique_networks,
                total_hosts_scanned=self._hosts_scanned,
                scan_time=time.time() - start_time,
                error=str(e)
            )
    
    def scan_ip_range(self, start_ip: str, end_ip: str) -> ScanResult:
        """
        Сканирует диапазон IP адресов
        
        Args:
            start_ip: Начальный IP
            end_ip: Конечный IP
            
        Returns:
            ScanResult с найденными серверами
        """
        import time
        start_time = time.time()
        
        self._found_servers = []
        self._hosts_scanned = 0
        
        try:
            start = int(ipaddress.IPv4Address(start_ip))
            end = int(ipaddress.IPv4Address(end_ip))
            
            if start > end:
                start, end = end, start
            
            queue = Queue()
            for ip_int in range(start, end + 1):
                queue.put(str(ipaddress.IPv4Address(ip_int)))
            
            total_hosts = end - start + 1
            num_threads = min(self.max_threads, total_hosts)
            
            threads = []
            for _ in range(num_threads):
                t = threading.Thread(target=self._scan_worker, args=(queue,))
                t.daemon = True
                t.start()
                threads.append(t)
            
            queue.join()
            
            return ScanResult(
                status=ScanStatus.SUCCESS,
                servers=sorted(list(set(self._found_servers))),
                scanned_networks=[f"{start_ip}-{end_ip}"],
                total_hosts_scanned=self._hosts_scanned,
                scan_time=time.time() - start_time
            )
            
        except Exception as e:
            return ScanResult(
                status=ScanStatus.ERROR,
                error=str(e),
                scan_time=time.time() - start_time
            )
    
    def scan_hosts(self, hosts: List[str]) -> ScanResult:
        """
        Сканирует список хостов (IP или доменные имена)
        
        Args:
            hosts: Список IP адресов или доменов
            
        Returns:
            ScanResult с найденными серверами
        """
        import time
        start_time = time.time()
        
        self._found_servers = []
        self._hosts_scanned = 0
        
        try:
            queue = Queue()
            
            for host in hosts:
                try:
                    # Резолвим домен в IP
                    ip = socket.gethostbyname(host)
                    queue.put(ip)
                except socket.gaierror:
                    pass
            
            if queue.empty():
                return ScanResult(
                    status=ScanStatus.SUCCESS,
                    servers=[],
                    total_hosts_scanned=0,
                    scan_time=time.time() - start_time
                )
            
            num_threads = min(self.max_threads, queue.qsize())
            
            threads = []
            for _ in range(num_threads):
                t = threading.Thread(target=self._scan_worker, args=(queue,))
                t.daemon = True
                t.start()
                threads.append(t)
            
            queue.join()
            
            return ScanResult(
                status=ScanStatus.SUCCESS,
                servers=sorted(list(set(self._found_servers))),
                total_hosts_scanned=self._hosts_scanned,
                scan_time=time.time() - start_time
            )
            
        except Exception as e:
            return ScanResult(
                status=ScanStatus.ERROR,
                error=str(e),
                scan_time=time.time() - start_time
            )


# ==================== ПРОСТЫЕ ФУНКЦИИ-ОБЁРТКИ ====================

def find_servers_local(
    port: int = 1414,
    timeout: float = 0.5,
    max_threads: int = 100,
    on_found: Optional[Callable[[str, int], None]] = None
) -> ScanResult:
    """
    Поиск серверов во всех локальных сетях
    
    Args:
        port: Порт для поиска
        timeout: Таймаут подключения
        max_threads: Количество потоков
        on_found: Callback при нахождении (ip, port)
    
    Returns:
        ScanResult с результатами
    """
    scanner = NetworkScanner(
        port=port,
        timeout=timeout,
        max_threads=max_threads,
        on_found=on_found
    )
    return scanner.scan_local_networks()


def find_servers_global(
    start_ip: str,
    end_ip: str,
    port: int = 1414,
    timeout: float = 2.0,
    max_threads: int = 200,
    on_found: Optional[Callable[[str, int], None]] = None
) -> ScanResult:
    """
    Поиск серверов в диапазоне IP адресов
    
    Args:
        start_ip: Начальный IP
        end_ip: Конечный IP
        port: Порт для поиска
        timeout: Таймаут подключения
        max_threads: Количество потоков
        on_found: Callback при нахождении (ip, port)
    
    Returns:
        ScanResult с результатами
    """
    scanner = NetworkScanner(
        port=port,
        timeout=timeout,
        max_threads=max_threads,
        on_found=on_found
    )
    return scanner.scan_ip_range(start_ip, end_ip)


def get_local_interfaces() -> List[NetworkInterface]:
    """Получает список всех локальных сетевых интерфейсов"""
    scanner = NetworkScanner()
    return scanner.get_all_interfaces()