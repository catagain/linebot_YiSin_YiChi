import json
import os
from linebot import LineBotApi, WebhookHandler, LineBotApi
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import logging

# 設置基本日誌配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 取得正確的檔案路徑
def get_correct_path(filename):
    # 方案 1: 回到上一層目錄後找檔案
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(parent_dir, filename)
    logger.info(f"檔案路徑: {path}")
    return path

# 地址與照片 URL 對應表
ADDRESS_IMAGES = {
    "鷁欣緻境": "https://img2.591.com.tw/house/2023/10/18/169760391235376409.jpg!900x.water3.jpg",

    # 預設圖片，當找不到對應地址時使用
    "default": "https://media.discordapp.net/attachments/1426475448983883811/1446853326456098976/ChatGPT_Image_20251122_09_24_36.png?ex=69357eaa&is=69342d2a&hm=b8c89e10941cebd2e35525aa2bb286f19ae200fe2b5b7f5dd4f575c3deafc154&=&format=webp&quality=lossless&width=847&height=847"
}

def create_addresses_select_columns():
    try:
        # 顯示當前可用的建案圖片配置
        logger.info(f"當前可用的建案圖片配置: {ADDRESS_IMAGES}")
        
        # 使用正確路徑開啟檔案
        file_path = get_correct_path('addresses.json')
        logger.info(f"嘗試讀取建案列表文件: {file_path}")
        
        # 檢查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"建案列表文件不存在: {file_path}")
            return []
            
        with open(file_path, 'r', encoding='utf-8') as f:
            addresses = json.load(f)
            logger.info(f"成功讀取建案列表: {addresses}")

        # 檢查地址列表是否為空
        if not addresses:
            logger.warning("建案列表為空")
            return []  # 返回空列表，由呼叫者處理

        # 1. 準備 CarouselTemplate 的 Columns 列表
        columns = []
        logger.info("開始創建建案選單...")

        # 2. 遍歷地址列表，為每個地址建立一個 CarouselColumn
        for addr in addresses:
            # 從對應表取得圖片 URL，如果沒有則使用預設圖片
            image_url = ADDRESS_IMAGES.get(addr)
            
            if image_url:
                logger.info(f"建案 '{addr}' 使用對應圖片: {image_url}")
            else:
                image_url = ADDRESS_IMAGES["default"]
                logger.info(f"建案 '{addr}' 未找到對應圖片，使用預設圖片: {image_url}")
            
            # 每個地址 (addr) 成為一個 Column
            column = CarouselColumn(
                thumbnail_image_url = image_url,
                title=addr, 
                text='請確認並選擇此地址',
                actions=[
                    MessageAction(
                        label='選擇此地址', 
                        text=addr 
                    )
                ]
            )
            columns.append(column)
            logger.info(f"已添加建案 '{addr}' 到選單")

            # *** LINE CarouselTemplate 限制: 最多只能有 10 個 Columns ***
            if len(columns) >= 10:
                logger.warning("已達到LINE選單最大限制(10項)，後續建案將不顯示")
                break # 達到上限，停止添加

        logger.info(f"建案選單創建完成，共 {len(columns)} 項")
        return columns
    except Exception as e:
        logger.error(f"讀取地址檔案時發生錯誤: {e}", exc_info=True)
        return []  # 發生錯誤時返回空列表

# 如果直接運行此文件，測試函數
if __name__ == "__main__":
    print("測試建案圖片功能...")
    columns = create_addresses_select_columns()
    print(f"成功創建了 {len(columns)} 個建案選項")
    
    # 檢查 addresses.json 文件
    try:
        file_path = get_correct_path('addresses.json')
        print(f"addresses.json 文件路徑: {file_path}")
        
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"addresses.json 內容: {data}")
        else:
            print(f"警告: addresses.json 文件不存在於路徑: {file_path}")
            print("您需要創建這個文件並添加建案名稱列表")
            
            # 創建示例文件
            sample_data = ["鷁欣緻境", "示例建案2", "示例建案3"]
            print(f"創建示例 addresses.json 文件，內容: {sample_data}")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(sample_data, f, ensure_ascii=False, indent=2)
            print(f"示例文件已創建在: {file_path}")
    except Exception as e:
        print(f"檢查文件時發生錯誤: {e}")