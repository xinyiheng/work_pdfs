import requests
import json
import logging
from time import sleep

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FeishuWebhook:
    def __init__(self, webhook_url, api_key=None):
        self.webhook_url = webhook_url
        self.api_key = api_key
        
    def translate_to_chinese(self, text, is_title=False, is_theme=False):
        """Translate text to Chinese using OpenRouter API
        
        Args:
            text: The text to translate
            is_title: Whether this text is a title (if True, will keep original English after translation)
            is_theme: Whether this text is a theme/category
        """
        if not text or not text.strip():
            # 如果是空的theme，尝试返回一个默认分类
            if is_theme:
                return "未分类"
            return ""
            
        if not self.api_key:
            logger.warning("No API key provided for translation")
            return text
            
        try:
            logger.info(f"Translating text: {text[:50]}...")
            
            # For summary/content, use a more detailed instruction to ensure complete translation
            is_summary = len(text) > 100  # Assume longer texts are summaries
            
            if is_title:
                system_prompt = "你是一位专业的中英文翻译专家。请将以下英文书名翻译成中文，并在翻译后保留英文原文。"
                user_prompt = f"请将以下英文书名翻译成中文，并在翻译后保留英文原文，格式为'中文翻译（English Original）'：\n\n{text}"
            elif is_theme:
                system_prompt = "你是一位专业的图书分类专家。请将以下英文图书分类或主题翻译成中文。如果无法确定具体分类，请判断是小说(fiction)还是非小说(non-fiction)。"
                user_prompt = f"请翻译并确定以下图书分类/主题：\n\n{text}\n\n如果无法确定具体分类，请至少判断是'小说'还是'非小说'类别。"
            elif is_summary:
                system_prompt = "你是一位专业的中英文翻译专家。请将以下英文内容完整翻译成中文，确保保留原文的所有意思和细节，不要遗漏任何信息。"
                user_prompt = f"请将以下英文内容完整翻译成中文，确保不遗漏任何信息：\n\n{text}"
            else:
                system_prompt = "你是一位专业的中英文翻译专家。请将以下英文内容翻译成中文。"
                user_prompt = f"请将以下英文内容翻译成中文：\n\n{text}"
            
            logger.info("Sending translation request to OpenRouter API...")
            
            # Use qwen/qwen-turbo model for translation
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen/qwen-turbo",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                translated_text = result["choices"][0]["message"]["content"]
                logger.info(f"Translation successful. Result: {translated_text[:50]}...")
                
                # Check if any of the common fiction identifiers are in the theme
                fiction_indicators = ["fiction", "novel", "story", "thriller", "mystery", "fantasy", "sci-fi", "romance"]
                if is_theme and not translated_text.strip() or "请提供" in translated_text:
                    # Check if it's fiction or non-fiction based on the original text
                    if any(indicator in text.lower() for indicator in fiction_indicators):
                        return "小说"
                    else:
                        return "非小说"
                
                return translated_text
            else:
                logger.warning(f"Translation failed: {response.text}")
                if is_title:
                    # For titles, if translation fails, return in the format "Original (Original)"
                    return f"{text} ({text})"
                return text
                
        except Exception as e:
            logger.warning(f"Error during translation: {str(e)}")
            if is_title:
                # For titles, if translation fails, return in the format "Original (Original)"
                return f"{text} ({text})"
            return text
            
    def send_data(self, data, pdf_filename):
        """Send extracted book data to Feishu webhook"""
        if not data:
            logger.warning(f"No data to send for {pdf_filename}")
            return False
            
        try:
            logger.info(f"Sending {len(data)} book entries from {pdf_filename} to Feishu webhook")
            
            # Get the base filename without extension
            import os
            base_filename = os.path.splitext(os.path.basename(pdf_filename))[0]
            
            # List to store all processed data that will be sent to Feishu
            processed_data = []
            
            # 使用集合来跟踪已经处理过的书籍标题，防止重复发送
            processed_titles = set()
            
            # Format the message for Feishu
            for book in data:
                # Extract book information from the data, checking both English and Chinese field names
                title_value = book.get("title", book.get("标题", book.get("主题", "")))
                author_value = book.get("Author", book.get("作者", ""))
                summary_value = book.get("Summary", book.get("摘要", ""))
                publisher_value = book.get("Publisher", book.get("出版社", ""))
                date_value = book.get("Date", book.get("出版日期", book.get("日期", "")))
                theme_value = book.get("Theme", book.get("主题", ""))
                author_bio_value = book.get("Author_bio", book.get("作者简介", ""))
                
                # 创建一个唯一标识符，基于标题和作者，防止重复发送
                # 使用小写并去除空格，以便更准确地进行重复检测
                book_identifier = (title_value.lower().strip() + "_" + author_value.lower().strip())
                
                # 如果这本书已经处理过，则跳过
                if book_identifier in processed_titles:
                    logger.info(f"跳过重复的书籍: '{title_value}' by {author_value}")
                    continue
                
                # 将标识符添加到已处理集合中
                processed_titles.add(book_identifier)
                
                # Translate book information to Chinese, but keep author and publisher in original language
                # For title, keep original English after translation
                title = self.translate_to_chinese(title_value, is_title=True)
                # Keep author in original language
                author = author_value
                summary = self.translate_to_chinese(summary_value)
                # Keep publisher in original language
                publisher = publisher_value
                date = self.translate_to_chinese(date_value)
                theme = self.translate_to_chinese(theme_value, is_theme=True)
                author_bio = self.translate_to_chinese(author_bio_value)
                
                # Simple JSON format for database integration with standard English field names but Chinese content
                simple_json = {
                    "title": title,
                    "Author": author,
                    "Summary": summary,
                    "Publisher": publisher,
                    "Date": date,
                    "Theme": theme,
                    "Author_bio": author_bio,
                    "file_name": base_filename
                }
                
                # Add to processed data list
                processed_data.append(simple_json)
                
                logger.info(f"Sending data to Feishu with fields: {', '.join(simple_json.keys())}")
                
                # Send the simple JSON format
                response = requests.post(
                    self.webhook_url,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(simple_json, ensure_ascii=False).encode('utf-8')
                )
                
                # Check the response
                if response.status_code != 200:
                    logger.error(f"Failed to send data to Feishu: {response.text}")
                    return False
                else:
                    logger.info(f"Successfully sent data for '{title_value}' to Feishu")
                    
                # Feishu has rate limits, so add a small delay between messages
                sleep(1)
            
            # Save the processed data to results directory
            self._save_feishu_data(processed_data, pdf_filename)
            
            logger.info(f"Successfully sent all book data from {pdf_filename} to Feishu")
            return True
            
        except Exception as e:
            logger.error(f"Error sending data to Feishu webhook: {str(e)}")
            return False

    def _save_feishu_data(self, data, pdf_filename):
        """Save the data that was sent to Feishu to a local JSON file
        
        Args:
            data: The processed data that was sent to Feishu
            pdf_filename: The original PDF filename
        """
        if not data:
            logger.warning(f"No data to save for {pdf_filename}")
            return
            
        try:
            # Create results directory if it doesn't exist
            results_dir = "/Users/wangxiaohui/Downloads/2025上半年/results"
            if not os.path.exists(results_dir):
                os.makedirs(results_dir)
                logger.info(f"Created results directory: {results_dir}")
            
            # Get the base filename without extension
            base_filename = os.path.splitext(os.path.basename(pdf_filename))[0]
            
            # Create the output JSON file path for original data
            output_file = os.path.join(results_dir, f"{base_filename}.json")
            
            # Save the original data to a JSON file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Saved original data to {output_file}")
            
            # 创建翻译后的中文字段文件路径
            translated_cn_fields_file = os.path.join(results_dir, f"{base_filename}_translated_cn_fields.json")
            
            # 由于数据已经被翻译并发送到飞书，可以直接保存中文字段版本
            translated_data_cn_fields = []
            
            for book in data:
                translated_book_cn_fields = {
                    "标题": book.get("title", ""),
                    "作者": book.get("Author", ""),
                    "摘要": book.get("Summary", ""),
                    "出版社": book.get("Publisher", ""),
                    "出版日期": book.get("Date", ""),
                    "主题": book.get("Theme", ""),
                    "作者简介": book.get("Author_bio", ""),
                    "文件名": base_filename
                }
                
                translated_data_cn_fields.append(translated_book_cn_fields)
                
            # 保存中文字段版本
            with open(translated_cn_fields_file, 'w', encoding='utf-8') as f:
                json.dump(translated_data_cn_fields, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Saved translated data with Chinese fields to {translated_cn_fields_file}")
                
        except Exception as e:
            logger.error(f"Error saving data to file: {str(e)}")
            
    def save_translated_data(self, data, pdf_filename, use_chinese_fields=False):
        """Save translated book data to a local JSON file
        
        Args:
            data: The book data to translate and save
            pdf_filename: The name of the PDF file
            use_chinese_fields: If True, use Chinese field names; otherwise use original English field names
        """
        if not data:
            logger.warning(f"No data to save for {pdf_filename}")
            return False
            
        try:
            # 获取文件名（不含扩展名）
            import os
            base_filename = os.path.splitext(os.path.basename(pdf_filename))[0]
            
            # 创建结果目录（如果不存在）
            results_dir = "/Users/wangxiaohui/Downloads/2025上半年/results"
            if not os.path.exists(results_dir):
                os.makedirs(results_dir)
                
            # 首先检查是否已存在翻译后的文件
            translated_cn_fields_file = os.path.join(results_dir, f"{base_filename}_translated_cn_fields.json")
            
            if os.path.exists(translated_cn_fields_file):
                logger.info(f"翻译文件已存在，跳过重复翻译：{translated_cn_fields_file}")
                return True
                
            # 如果没有找到已翻译的文件，重新执行翻译
            logger.info(f"Saving translated data for {len(data)} book entries from {pdf_filename}")
            
            translated_data = []
            translated_data_cn_fields = []
            
            # 显示进度条
            total_books = len(data)
            print(f"开始翻译 {total_books} 本书的信息...")
            
            for i, book in enumerate(data):
                # 显示进度
                progress = int((i+1) / total_books * 100)
                print(f"\r翻译进度: [{progress}%] {'=' * (progress//5)}{' ' * (20-progress//5)}", end="")
                
                # 提取书籍信息
                title_value = book.get("title", book.get("标题", book.get("主题", "")))
                author_value = book.get("Author", book.get("作者", ""))
                summary_value = book.get("Summary", book.get("摘要", ""))
                publisher_value = book.get("Publisher", book.get("出版社", ""))
                date_value = book.get("Date", book.get("出版日期", book.get("日期", "")))
                theme_value = book.get("Theme", book.get("主题", ""))
                author_bio_value = book.get("Author_bio", book.get("作者简介", ""))
                
                # 翻译书籍信息
                title = self.translate_to_chinese(title_value, is_title=True)
                author = author_value  # 保持作者名为原文
                summary = self.translate_to_chinese(summary_value)
                publisher = publisher_value  # 保持出版社名为原文
                date = self.translate_to_chinese(date_value)
                theme = self.translate_to_chinese(theme_value, is_theme=True)
                author_bio = self.translate_to_chinese(author_bio_value)
                
                # 创建翻译后的书籍条目（英文字段）
                translated_book = {
                    "title": title,
                    "Author": author,
                    "Summary": summary,
                    "Publisher": publisher,
                    "Date": date,
                    "Theme": theme,
                    "Author_bio": author_bio,
                    "original_title": title_value
                }
                
                # 创建翻译后的书籍条目（中文字段）
                translated_book_cn_fields = {
                    "标题": title,
                    "作者": author,
                    "摘要": summary,
                    "出版社": publisher,
                    "出版日期": date,
                    "主题": theme,
                    "作者简介": author_bio,
                    "文件名": base_filename
                }
                
                translated_data.append(translated_book)
                translated_data_cn_fields.append(translated_book_cn_fields)
            
            print("\n翻译完成!")
            
            # 保存翻译后的数据（使用中文字段）
            with open(translated_cn_fields_file, 'w', encoding='utf-8') as f:
                json.dump(translated_data_cn_fields, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Translated data saved to {translated_cn_fields_file}")
            return True
                
        except Exception as e:
            logger.error(f"Error saving translated data: {str(e)}")
            return False
