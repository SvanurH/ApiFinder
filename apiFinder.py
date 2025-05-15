import argparse
import importlib.util
import importlib
from pathlib import Path
from urllib.parse import urljoin
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from bs4 import BeautifulSoup
import requests
from typing import List, Set, Optional, Dict, Tuple
from colorama import init, Fore, Style
from abc import ABC, abstractmethod

# 初始化 colorama
init(autoreset=True)

# 禁用所有警告（请谨慎使用）
warnings.filterwarnings('ignore')


class RequestsInterface(ABC):
    @abstractmethod
    def get(self, url: str, verify_ssl: bool = False) -> Optional[bytes]:
        pass


class ParsedInterface(ABC):
    @abstractmethod
    def extract_scripts(self, html: bytes) -> List[str]:
        pass

    @abstractmethod
    def extract_urls_from_js(self, js: bytes) -> List[str]:
        pass

    @abstractmethod
    def clean(self, paths: Set[str]) -> List[str]:
        pass


class DefaultRequests(RequestsInterface):
    """封装 requests，统一超时、headers、错误处理"""
    DEFAULT_TIMEOUT = 5
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.93 Safari/537.36"
        ),
    }

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, headers: Optional[Dict[str, str]] = None):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        if headers:
            self.session.headers.update(headers)

    def get(self, url: str, verify_ssl: bool = False) -> Optional[bytes]:
        """
        使用get方法下载html或者js文件代码
        :param url:
        :param verify_ssl:
        :return:
        """
        try:
            if not verify_ssl:
                try:
                    from requests.packages.urllib3.exceptions import InsecureRequestWarning
                    from requests.packages.urllib3 import disable_warnings
                except ImportError:
                    import urllib3
                    from urllib3.exceptions import InsecureRequestWarning
                    disable_warnings = urllib3.disable_warnings
                disable_warnings(InsecureRequestWarning)

            resp = self.session.get(url, timeout=self.timeout, verify=verify_ssl)
            resp.raise_for_status()
            print(Fore.GREEN + f"[+] 下载成功: {url}")
            return resp.content
        except Exception as e:
            print(Fore.RED + f"[!] 请求失败: {url} -> {e}")
            return None


class DefaultParsed(ParsedInterface):
    """解析 HTML 和 JS 中的脚本及 URL"""
    DEFAULT_RULES = r"""
	  (?:"|')                               # Start newline delimiter
	  (
	    ((?:/|\.\./|\./)                    # Start with /,../,./
	    [^"'><,;| *()(%%$^/\\\[\]]          # Next character can't be...
	    [^"'><,;|()]{1,})                   # Rest of the characters can't be
	    |
	    ([a-zA-Z0-9_\-/]{1,}/               # Relative endpoint with /
	    [a-zA-Z0-9_\-/]{1,}                 # Resource name
	    \.(?:[a-zA-Z]{1,4}|action)          # Rest + extension (length 1-4 or action)
	    (?:[\?|/][^"|']{0,}|))              # ? mark with parameters
	    |
	    ([a-zA-Z0-9_\-]{1,}                 # filename
	    \.(?:php|asp|aspx|jsp|json|
	         action|html|js|txt|xml)             # . + extension
	    (?:\?[^"|']{0,}|))                  # ? mark with parameters
	  )
	  (?:"|')                               # End newline delimiter
	"""
    RULE = re.compile(DEFAULT_RULES, re.VERBOSE)

    def extract_scripts(self, html: bytes) -> List[str]:
        """
        从html文件中获取script标签中的js地址
        :param html: html源码
        :return: url列表
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            scripts = [tag['src'] for tag in soup.find_all('script', src=True)]
            print(Fore.CYAN + f"[~] 找到 {len(scripts)} 个 script 标签")
            return scripts
        except Exception as e:
            print(Fore.RED + f"[!] HTML 解析失败: {e}")
            return []

    def extract_urls_from_js(self, js: bytes) -> List[str]:
        """
        获取js代码，从中提取api接口
        :param js:
        :return:
        """
        try:
            text = js.decode('utf-8', errors='ignore')
        except Exception as e:
            print(Fore.RED + f"[!] JS 解码失败: {e}")
            return []
        urls = [m.group(1) for m in self.RULE.finditer(text)]
        # print(Fore.CYAN + f"[~] 从 JS 提取到 {len(urls)} 个 URL")
        return urls

    def clean(self, paths: Set[str]) -> List[str]:
        cleaned = sorted({p.strip() for p in paths if p.strip()}, key=lambda x: x)
        print(Fore.BLUE + f"[=] 总计 {len(cleaned)} 个去重后 URL")
        return cleaned


# 动态加载自定义类

def load_custom(path: Optional[str], cls_names: Tuple[str, str]) -> Tuple[type, type]:
    parsed_name, req_name = cls_names
    if not path:
        return DefaultParsed, DefaultRequests
    try:
        if path.endswith('.py'):
            p = Path(path)
            spec = importlib.util.spec_from_file_location(p.stem, p)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore
        else:
            module = importlib.import_module(path)

        if cls_names[0]:
            parsed = getattr(module, parsed_name, DefaultParsed)
            print(Fore.GREEN + f"[+] 使用自定义解析类: {parsed.__name__}")
        else:
            parsed = DefaultParsed
        if cls_names[1]:
            req = getattr(module, req_name, DefaultRequests)
            print(Fore.GREEN + f"[+] 使用自定义请求类: {req.__name__}")
        else:
            req = DefaultRequests
        return parsed, req
    except Exception as e:
        print(Fore.YELLOW + f"[!] 加载自定义模块失败 ({path}): {e}, 使用默认类")
        return DefaultParsed, DefaultRequests


def process_target(url: str,
                   parsed_inst: ParsedInterface,
                   req_inst: RequestsInterface,
                   verify_ssl: bool) -> Set[str]:
    found: Set[str] = set()
    html = req_inst.get(url, verify_ssl)
    if not html:
        return found
    scripts = parsed_inst.extract_scripts(html)
    full_js_urls = [urljoin(url, s) for s in scripts]
    with ThreadPoolExecutor() as pool:
        futures = {pool.submit(req_inst.get, js_url, verify_ssl): js_url for js_url in full_js_urls}
        for f in as_completed(futures):
            js = f.result()
            if js:
                found.update(parsed_inst.extract_urls_from_js(js))
    return found


def main():
    parser = argparse.ArgumentParser(description="JS 内部 URL 挖掘工具")
    parser.add_argument('-u', '--url', help='目标 URL', required=False)
    parser.add_argument('-f', '--file', help='URL 列表文件', required=False)
    parser.add_argument('-cm', '--custom_module', help='自定义模块路径/名', required=False)
    parser.add_argument('-pn', '--parsed_name', help='自定义解析类名')
    parser.add_argument('-rn', '--request_name', help='自定义请求类名')
    parser.add_argument('-w', '--workers', type=int, default=10, help='线程数')
    parser.add_argument('--ssl', action='store_true', help='启用 SSL 验证')
    parser.add_argument('-o', '--output', help='保存结果到文件', required=False)

    args = parser.parse_args()
    if not args.url and not args.file:
        parser.error('请通过 -u 或 -f 提供 URL')
    if args.custom_module and not (args.parsed_name or args.request_name):
        parser.error('使用了 -cm 参数，则必须指定 -pn 或 -rn')
    urls: List[str] = []
    if args.file:
        urls += [l.strip() for l in Path(args.file).read_text(encoding='utf-8').splitlines() if l.strip()]
    if args.url:
        urls.append(args.url)
    if not urls:
        parser.error('请通过 -u 或 -f 提供 URL')

    parsed_cls, req_cls = load_custom(args.custom_module, (args.parsed_name, args.request_name))
    parsed_inst = parsed_cls()
    req_inst = req_cls()

    all_urls: Set[str] = set()
    for u in urls:
        print(Fore.MAGENTA + f"[+] 开始处理: {u}")
        result = process_target(u, parsed_inst, req_inst, args.ssl)
        all_urls |= result

    # 只打印 URL，方便复制
    cleaned = parsed_inst.clean(all_urls)
    print(Style.BRIGHT + Fore.WHITE + "\n提取到的 URL 列表:")
    for url in cleaned:
        print(url)
    if args.output:

        file = open(args.output, 'a+', encoding='utf-8')
        for url in cleaned:
            file.write(url + '\n')
        file.close()


if __name__ == '__main__':
    main()
