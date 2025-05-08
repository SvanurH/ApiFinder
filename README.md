
# JS 内部 URL 挖掘工具

> 一个基于 Python 的命令行工具，用于发现目标网站中 JavaScript 文件中的 API 接口地址。

---

## ✨ 特点

- **高效并发**：内置线程池，支持多线程并发下载与解析，提高抓取速度。
- **灵活扩展**：支持加载自定义解析类与请求类，让你能轻松适配特殊场景。
- **智能提取**：基于正则与 BeautifulSoup，精准提取 `<script>` 标签与 JS 文件中的接口地址。
- **去重排序**：自动清洗、去重并排序最后的 URL 列表，输出更整洁。
- **SSL 可选**：通过参数可开启或关闭 HTTPS 证书验证，兼容更多测试环境。
- **丰富输出**：命令行直接打印提取结果，并支持将结果保存到本地文件。

## 🚀 安装

1. 克隆仓库：

   ```bash
   git clone https://github.com/yourname/js-url-finder.git
   cd js-url-finder
   ```


2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

> 依赖包括：`requests`、`BeautifulSoup4`、`colorama` 等。

## 🛠️ 使用方法

```bash
python apiFinder.py [参数]
```

| 参数                | 说明                        | 可选 / 默认       |
| ----------------- | ------------------------- | ------------- |
| `-u`, `--url`     | 目标 URL                    | 必填 或 `-f`     |
| `-f`, `--file`    | 包含多个目标 URL 的文件路径，每行一个 URL | 必填 或 `-u`     |
| `-cm`             | 自定义模块路径或模块名               | 可选            |
| `-pn`             | 自定义解析类名                   | 可选（需配合 `-cm`） |
| `-rn`             | 自定义请求类名                   | 可选（需配合 `-cm`） |
| `-w`, `--workers` | 并发线程数                     | 可选 / `10`     |
| `--ssl`           | 启用 SSL 证书验证               | 可选            |
| `-o`, `--output`  | 将结果写入指定文件                 | 可选            |

### 示例

1. **单 URL 处理**：

   ```bash
   python main.py -u https://example.com
   ```

2. **批量处理**：

   ```bash
   python main.py -f urls.txt -o result.txt
   ```

3. **加载自定义解析类**：

   ```bash
   python main.py -u https://example.com -cm custom_parser.py -pn MyParser
   ```

## 📂 自定义扩展

* 在 `-cm` 指定的路径下提供 Python 模块，模块中需包含自定义的解析类与/或请求类。
* 使用 `-pn` 与 `-rn` 指定类名，继承自 `ParsedInterface` 和 `RequestsInterface` 即可。
* 如果加载失败，会自动回退到默认实现。

`RequestsInterface`:
```python
from abc import ABC, abstractmethod
from typing import Optional

class RequestsInterface(ABC):
    @abstractmethod
    def get(self, url: str, verify_ssl: bool = False) -> Optional[bytes]:
        """
        实现 HTTP GET 请求，返回响应内容（bytes）或 None。
        """
        pass
```

`ParsedInterface`:
```python
from abc import ABC, abstractmethod
from typing import List, Set

class ParsedInterface(ABC):
    @abstractmethod
    def extract_scripts(self, html: bytes) -> List[str]:
        """
        从 HTML 内容中提取 script 标签的 src 属性值。
        """
        pass

    @abstractmethod
    def extract_urls_from_js(self, js: bytes) -> List[str]:
        """
        从 JS 内容中提取 URL 或路径。
        """
        pass

    @abstractmethod
    def clean(self, paths: Set[str]) -> List[str]:
        """
        对提取到的路径进行清洗、去重和排序。
        """
        pass

```



