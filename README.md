# PDF Book Catalog Extractor

这个应用程序可以自动从出版社的书讯PDF中提取结构化信息，并将其发送到飞书文档。

## 功能

- 使用 Google Gemini 2.0 Flash 模型（通过 OpenRouter）进行图像识别和信息提取
- 提取书籍的标题、作者、摘要、出版商、日期、主题、作者简介和原始标题
- 自动监控文件夹中的新PDF文件
- 将提取的信息发送到飞书文档
- 将结果保存为JSON文件
- **断点续传**: 当处理中断时，重启应用会自动跳过已处理文件，并从上次中断的页码继续处理部分完成的PDF
- **特殊页面处理**: 对纯图书封面展示页面进行特殊处理，在summary字段中添加说明

## 安装

1. 安装依赖:

```bash
pip install -r requirements.txt
```

2. 确保已经设置好环境变量（已在.env文件中配置）:
   - `OPENROUTER_API_KEY`: OpenRouter API密钥
   - `FEISHU_WEBHOOK_URL`: 飞书webhook URL

## 使用方法

### 命令行选项

```bash
python main.py [选项]
```

可用选项:

| 选项 | 说明 |
|------|------|
| `--watch` | 启动文件监视器，监视Files目录中的新PDF文件并处理它们 |
| `--test` | 运行单个PDF测试（使用默认测试文件） |
| `--test-pdf FILE` | 指定要处理的PDF文件路径 |
| `--process-all` | 处理Files目录中的所有PDF文件（会跳过已处理的文件） |
| `--max-pages N` | 要处理的最大页数，默认为None（处理整个PDF） |
| `--limit N` | 处理所有文件时的最大文件数限制，默认为0（处理所有文件） |
| `--force` | 强制重新处理所有文件，忽略之前的处理进度 |

### 常用命令示例

#### 测试单个文件

```bash
python main.py --test-pdf "文件名.pdf"
```

#### 处理所有未处理的文件

```bash
python main.py --process-all
```

#### 强制重新处理所有文件

```bash
python main.py --process-all --force
```

#### 启动文件监视器（自动处理新添加的PDF）

```bash
python main.py --watch
```

#### 限制处理页数（用于测试）

```bash
python main.py --test-pdf "文件名.pdf" --max-pages 10
```

#### 检查未处理的文件

```bash
python check_unprocessed.py
```

## 工作流程

1. **单个文件处理**：使用`--test-pdf`选项指定要处理的PDF文件，系统会将其转换为图像，然后使用AI模型提取书籍信息。

2. **批量处理**：使用`--process-all`选项处理Files目录中的所有PDF文件，系统会自动跳过已处理的文件，只处理新文件或部分处理的文件。

3. **文件监视**：使用`--watch`选项启动文件监视器，系统会监视Files目录中的新文件，一旦检测到新的PDF文件，就会自动开始处理。

4. **断点续传**：如果处理过程中断，重新运行程序时会自动从上次处理的页码继续处理，无需重新开始。

## 文件结构

- `main.py`: 主程序入口，包含命令行参数解析和主要处理逻辑
- `pdf_processor.py`: PDF处理和信息提取，负责将PDF转换为图像并使用AI模型提取信息
- `webhook_handler.py`: 发送数据到飞书webhook，并保存翻译后的数据
- `file_watcher.py`: 监控文件夹中的新文件，使用watchdog库实现
- `check_unprocessed.py`: 检查未处理或部分处理的PDF文件
- `requirements.txt`: 依赖列表
- `.env`: 环境变量配置
- `progress.pkl`: 处理进度记录文件，用于断点续传
- `Files/`: 存放待处理的PDF文件
- `results/`: 存放提取结果的JSON文件

## 注意事项

- 确保PDF文件放在`Files`目录中
- 提取的结果将保存在`results`目录中，包括原始数据和翻译后的数据
- 程序会自动创建日志文件`pdf_extraction.log`
- 处理进度会自动保存在`progress.pkl`文件中，断点续传功能不需要额外配置
- 系统默认处理PDF的全部页面，以确保完整提取所有书籍信息
- 对于纯图书封面展示页面，系统会在summary字段中添加特殊说明
