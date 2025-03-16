# PDF Book Catalog Extractor

这个应用程序可以自动从出版社的书讯PDF中提取结构化信息，并将其发送到飞书文档。

## 功能

- 使用 Google Gemini 2.0 Flash 模型（通过 OpenRouter）进行图像识别和信息提取
- 提取书籍的标题、作者、摘要、出版商、日期、主题、作者简介和原始标题
- 自动监控文件夹中的新PDF文件
- 将提取的信息发送到飞书文档
- 将结果保存为JSON文件
- **断点续传**: 当处理中断时，重启应用会自动跳过已处理文件，并从上次中断的页码继续处理部分完成的PDF

## 安装

1. 安装依赖:

```bash
pip install -r requirements.txt
```

2. 确保已经设置好环境变量（已在.env文件中配置）:
   - `OPENROUTER_API_KEY`: OpenRouter API密钥
   - `FEISHU_WEBHOOK_URL`: 飞书webhook URL

## 使用方法

### 测试单个文件

```bash
python main.py --test /path/to/your/file.pdf
```

### 处理所有现有文件

```bash
python main.py --process-all
```

### 启动文件监控（自动处理新添加的PDF）

```bash
python main.py
```

## 文件结构

- `main.py`: 主程序入口
- `pdf_processor.py`: PDF处理和信息提取
- `webhook_handler.py`: 发送数据到飞书webhook
- `file_watcher.py`: 监控文件夹中的新文件
- `requirements.txt`: 依赖列表
- `.env`: 环境变量配置

## 注意事项

- 确保PDF文件放在`Files`目录中
- 提取的结果将保存在`results`目录中
- 程序会自动创建日志文件`pdf_extraction.log`
- 处理进度会自动保存，断点续传功能不需要额外配置
