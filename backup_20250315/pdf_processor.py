import os
import json
from pathlib import Path
import tempfile
import logging
import time
from pdf2image import convert_from_path
import requests
import base64
import io
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost",  # Required by OpenRouter
            "X-Title": "PDF Book Extractor"       # Optional but good practice
        }
        logger.info(f"Initialized PDF processor with OpenRouter API key: {api_key[:5]}...{api_key[-5:]}")
        
    def encode_image(self, image, quality=85, max_size=(800, 800)):
        """Encode PIL Image to base64 string with optimization"""
        # Resize image if it's too large (to reduce API costs and improve speed)
        width, height = image.size
        if width > max_size[0] or height > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            logger.info(f"Resized image from {width}x{height} to {image.size}")
            
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    def is_toc_or_title_page(self, content):
        """Check if a page is a table of contents or title page"""
        if not content:
            return True
            
        indicators = ['contents', 'table of contents', 'catalog', 'index', 'guide']
        content_lower = content.lower()
        
        # Check if page has very little text or contains TOC indicators
        if len(content.strip()) < 50:
            return True
            
        for indicator in indicators:
            if indicator in content_lower:
                # If the indicator is the primary content, it's likely a TOC
                if content_lower.count(indicator) > 0 and len(content_lower.split()) < 30:
                    return True
        
        return False
    
    def process_pdf(self, pdf_path, max_pages=None, start_page=2):
        """
        处理PDF文件并提取结构化信息
        
        Args:
            pdf_path: PDF文件路径
            max_pages: 最大处理页数，如果为None则处理所有页面
            start_page: 开始处理的页码（从0开始计数）
        
        Returns:
            提取的结构化信息列表
        """
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return []
            
        try:
            # Convert PDF to images
            logger.info(f"Converting PDF to images: {pdf_path}")
            images = self.pdf_to_images(pdf_path)
            
            if not images:
                logger.error(f"Failed to convert PDF to images: {pdf_path}")
                return []
                
            logger.info(f"Converted PDF to {len(images)} images")
            
            # Process each page
            all_book_data = []
            
            # 设置处理的页面范围
            end_page = len(images) if max_pages is None else min(start_page + max_pages, len(images))
            
            # 显示总体处理进度信息
            total_pages = end_page - start_page
            logger.info(f"将处理PDF的页码范围: {start_page+1}-{end_page} (共{total_pages}页)")
            print(f"\n开始处理PDF《{os.path.basename(pdf_path)}》，共{total_pages}页...")
            
            # 处理每一页
            for i in range(total_pages):
                actual_page = i + start_page
                # 显示详细的进度条
                progress_percent = int((i + 1) / total_pages * 100)
                progress_bar = "=" * (progress_percent // 2) + " " * (50 - progress_percent // 2)
                print(f"\r处理进度: [{progress_percent}%] [{progress_bar}] 页码:{actual_page+1}/{end_page}", end="")
                
                # Check if the page is within the range of available images
                if actual_page >= len(images):
                    logger.warning(f"Page {actual_page+1} is out of range. PDF only has {len(images)} pages.")
                    break
                    
                image = images[actual_page]
                
                if self.is_toc_or_title_page(image):
                    logger.info(f"Skipping page {actual_page+1} as it appears to be a title or TOC page")
                    continue
                
                try:
                    page_start_time = time.time()
                    logger.info(f"Processing page {i+1}/{end_page-start_page} (page {actual_page+1}/{len(images)} in PDF)")
                    
                    # 更新处理进度
                    self.update_progress_callback(pdf_path, i + start_page)
                    
                    # Encode image to base64
                    base64_image = self.encode_image(image)
                    
                    # Create the request payload for OpenRouter with Gemini model
                    # Format for OpenRouter with Gemini model
                    payload = {
                        "model": "google/gemini-2.0-flash-001",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": """You are a book catalog information extractor specialized in publisher rights guides. Analyze the given book catalog page 
                                        and extract structured information about ALL books found on the page. 
                                        
                                        If the page is ONLY a table of contents, index, or title page with NO book information, respond with {"is_book_page": false}.
                                        
                                        IMPORTANT: Many pages will contain information for MULTIPLE books. Each book typically has its own section with title, author, and description.
                                        Extract information for EACH book separately. If you see multiple books on one page, extract ALL of them.
                                        
                                        For book pages, extract the following details in a structured format:
                                        - title: The book title in English
                                        - Author: Author name(s)
                                        - Summary: A brief summary or description of the book
                                        - Publisher: Publisher name
                                        - Date: Publication date
                                        - Theme: Categorize the book (e.g., Business, Self-help, Fiction, etc.)
                                        - Author_bio: Brief author biography
                                        
                                        Extract ALL book information from this catalog page and format it as JSON. 
                                        If there are multiple books on the page, return an array of book objects.
                                        If this is a table of contents or title page with NO book information, just respond with {"is_book_page": false}.
                                        
                                        EXAMPLE RESPONSE WITH MULTIPLE BOOKS:
                                        {
                                          "is_book_page": true,
                                          "books": [
                                            {
                                              "title": "Book Title 1",
                                              "Author": "Author Name 1",
                                              "Summary": "Summary of book 1...",
                                              ...
                                            },
                                            {
                                              "title": "Book Title 2",
                                              "Author": "Author Name 2",
                                              "Summary": "Summary of book 2...",
                                              ...
                                            }
                                          ]
                                        }
                                        """
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 2000
                    }
                    
                    # Log the API request details for debugging
                    logger.info(f"Making API request to OpenRouter with API key: {self.api_key[:5]}...{self.api_key[-5:]}")
                    
                    # Make the API request with retry logic
                    max_retries = 3
                    retry_delay = 2
                    
                    for retry in range(max_retries):
                        try:
                            logger.info(f"Sending page {actual_page+1} to Gemini model (attempt {retry+1}/{max_retries})...")
                            response = requests.post(
                                self.api_url,
                                headers=self.headers,
                                json=payload,
                                timeout=120  # Increased timeout for image processing
                            )
                            
                            # Log the response for debugging
                            logger.info(f"Response status code: {response.status_code}")
                            
                            if response.status_code == 200:
                                break
                            elif response.status_code == 429:  # Rate limit
                                wait_time = retry_delay * (retry + 1)
                                logger.warning(f"Rate limited. Waiting {wait_time} seconds before retry...")
                                time.sleep(wait_time)
                            else:
                                logger.error(f"API request failed: {response.status_code} - {response.text}")
                                if retry < max_retries - 1:
                                    wait_time = retry_delay * (retry + 1)
                                    logger.info(f"Retrying in {wait_time} seconds...")
                                    time.sleep(wait_time)
                                else:
                                    logger.error("Max retries reached. Skipping this page.")
                                    break
                        except Exception as e:
                            logger.error(f"Request error: {str(e)}")
                            if retry < max_retries - 1:
                                wait_time = retry_delay * (retry + 1)
                                logger.info(f"Retrying in {wait_time} seconds...")
                                time.sleep(wait_time)
                            else:
                                logger.error("Max retries reached. Skipping this page.")
                                break
                    
                    if response.status_code != 200:
                        logger.error(f"Failed to process page {actual_page+1} after {max_retries} attempts. Skipping.")
                        continue
                        
                    response_data = response.json()
                    logger.info(f"Response data keys: {list(response_data.keys())}")
                    result_text = response_data['choices'][0]['message']['content']
                    
                    # Try to parse the JSON response
                    try:
                        # Extract JSON from the response if it contains other text
                        json_start = result_text.find('{')
                        json_end = result_text.rfind('}') + 1
                        
                        if json_start >= 0 and json_end > json_start:
                            json_str = result_text[json_start:json_end]
                            result = json.loads(json_str)
                            
                            # Check if it's a book page
                            if result.get("is_book_page") is False:
                                logger.info(f"Page {actual_page+1} is not a book page (TOC, title, etc.)")
                                continue
                                
                            # 打印原始JSON结果，便于调试
                            logger.debug(f"Page {actual_page+1} JSON result: {json.dumps(result, indent=2)}")
                            
                            # 处理可能的多本书的情况
                            if "books" in result and isinstance(result["books"], list):
                                logger.info(f"Found {len(result['books'])} books on page {actual_page+1}")
                                # 添加每本书的来源页码信息
                                for book in result["books"]:
                                    book["page_number"] = actual_page + 1
                                    all_book_data.append(book)
                            # 兼容单本书的情况（老格式）
                            elif result.get("is_book_page", True) and result.get("title"):
                                logger.info(f"Found a single book on page {actual_page+1}: {result.get('title', 'Untitled')}")
                                result["page_number"] = actual_page + 1
                                all_book_data.append(result)
                            # 尝试检测书籍信息但格式不标准的情况
                            elif any(key in result for key in ["title", "Author", "Summary"]):
                                logger.info(f"Found potential book information on page {actual_page+1} in non-standard format")
                                result["page_number"] = actual_page + 1
                                all_book_data.append(result)
                            else:
                                logger.warning(f"Page {actual_page+1} contains JSON but no recognizable book information")
                                
                            page_time = time.time() - page_start_time
                            logger.info(f"Successfully processed page {actual_page+1} in {page_time:.2f} seconds")
                        else:
                            logger.warning(f"Could not find valid JSON in response for page {actual_page+1}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON from response for page {actual_page+1}")
                        logger.debug(f"Raw response: {result_text}")
                
                except Exception as e:
                    logger.error(f"Error processing page {actual_page+1}: {str(e)}")
                    
            print("\n")
            total_time = time.time() - start_time
            logger.info(f"PDF processing completed in {total_time:.2f} seconds. Extracted {len(all_book_data)} book entries.")
            return all_book_data
                
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            return []

    def process_and_format(self, pdf_file, max_pages=None, start_page=2):
        """Process PDF and format results according to the required structure"""
        results = self.process_pdf(pdf_file, max_pages, start_page)
        
        formatted_results = []
        for result in results:
            formatted_result = {
                "title": result.get("title", ""),
                "Author": result.get("Author", ""),
                "Summary": result.get("Summary", ""),
                "Publisher": result.get("Publisher", ""),
                "Date": result.get("Date", ""),
                "Theme": result.get("Theme", ""),
                "Author_bio": result.get("Author_bio", ""),
                "original_title": result.get("original_title", "")
            }
            formatted_results.append(formatted_result)
            
        return formatted_results
        
    def update_progress_callback(self, pdf_path, current_page):
        """进度更新回调函数（可以被主程序重写）"""
        pass  # 默认什么都不做，主程序可以设置自己的回调逻辑

    def pdf_to_images(self, pdf_path):
        try:
            # Convert PDF to images
            with tempfile.TemporaryDirectory() as temp_dir:
                logger.info("Converting PDF to images...")
                start_time = time.time()
                images = convert_from_path(pdf_path, dpi=150, output_folder=temp_dir)
                conversion_time = time.time() - start_time
                logger.info(f"PDF conversion completed in {conversion_time:.2f} seconds. Found {len(images)} pages.")
                return images
        except Exception as e:
            logger.error(f"Error converting PDF to images: {str(e)}")
            return []
