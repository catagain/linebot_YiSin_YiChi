from linebot import LineBotApi
from linebot.models import RichMenu, RichMenuArea, RichMenuBounds, MessageAction
from PIL import Image  # 需要安裝：pip install Pillow

from dotenv import load_dotenv
import os
load_dotenv()

# 獲取 LINE_CHANNEL_ACCESS_TOKEN
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

# API 客戶端
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)

# 直接使用 PNG 圖片路徑
PNG_IMAGE_PATH = "image/richmenu.png"  # 確保這個路徑是正確的

# 刪除現有的 Rich Menu
def delete_rich_menu():
    """刪除所有現有的 Rich Menu"""
    try:
        # 獲取所有 Rich Menu ID
        rich_menu_list = line_bot_api.get_rich_menu_list()
        
        # 刪除每個 Rich Menu
        for rich_menu in rich_menu_list:
            line_bot_api.delete_rich_menu(rich_menu.rich_menu_id)
            print(f"已刪除 Rich Menu: {rich_menu.rich_menu_id}")
        
        print("所有 Rich Menu 已刪除")
        return True
    except Exception as e:
        print(f"刪除 Rich Menu 失敗: {str(e)}")
        return False

def check_image_size(image_path):
    """檢查圖片尺寸是否符合要求"""
    try:
        img = Image.open(image_path)
        width, height = img.size
        print(f"圖片尺寸: {width}x{height}")
        
        if width != 1242 or height != 847:
            print(f"警告: 圖片尺寸 {width}x{height} 不符合 LINE Rich Menu 要求 (1242x847)")
            return False
            
        # 檢查檔案大小
        file_size = os.path.getsize(image_path) / 1024  # KB
        print(f"圖片檔案大小: {file_size:.2f} KB")
        
        if file_size > 1000:  # 1MB = 1000KB
            print(f"警告: 圖片檔案大小 {file_size:.2f} KB 超過 LINE Rich Menu 限制 (1000 KB)")
            return False
            
        return True
    except Exception as e:
        print(f"檢查圖片失敗: {str(e)}")
        return False

def setup_rich_menu():
    """創建並設置 Rich Menu"""
    
    # 先刪除現有的 Rich Menu
    delete_rich_menu()
    
    # 檢查 PNG 圖片是否存在
    if not os.path.exists(PNG_IMAGE_PATH):
        print(f"圖片不存在: {PNG_IMAGE_PATH}")
        return None
    
    # 檢查圖片尺寸
    if not check_image_size(PNG_IMAGE_PATH):
        print("圖片不符合 LINE Rich Menu 要求，請修正後再試")
        return None
    
    # 創建 Rich Menu 物件
    rich_menu_to_create = RichMenu(
        size={"width": 1242, "height": 847},
        selected=True,
        name="Main Menu",
        chat_bar_text="點我開啟選單",
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(x=0, y=424, width=414, height=424),
                action=MessageAction(label="修改個人資訊", text="修改個人資訊")
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=0, y=0, width=1050, height=424),
                action=MessageAction(label="我要報修", text="我要報修")
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=1050, y=0, width=192, height=424),
                action=MessageAction(label="確認交屋", text="確認交屋")  # 修改為"確認交屋"
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=414, y=424, width=414, height=424),
                action=MessageAction(label="我的個人資料", text="我的個人資料")
            ),
            RichMenuArea(
                bounds=RichMenuBounds(x=828, y=424, width=414, height=424),
                action=MessageAction(label="私訊客服", text="私訊客服")
            )
        ]
    )
    
    # 創建 Rich Menu
    try:
        rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu_to_create)
        print(f"成功創建 Rich Menu，ID: {rich_menu_id}")
    except Exception as e:
        print(f"創建 Rich Menu 失敗: {str(e)}")
        return None
    
    # 上傳 Rich Menu 圖片
    try:
        with open(PNG_IMAGE_PATH, 'rb') as f:
            line_bot_api.set_rich_menu_image(rich_menu_id, "image/png", f)
            print(f"成功上傳 Rich Menu 圖片")
    except Exception as e:
        print(f"上傳 Rich Menu 圖片失敗：{str(e)}")
        print(f"錯誤詳情：{e}")  # 顯示更多錯誤詳情
        return None
    
    # 設置為預設 Rich Menu
    try:
        line_bot_api.set_default_rich_menu(rich_menu_id)
        print("已成功設置為預設 Rich Menu")
    except Exception as e:
        print(f"設置預設 Rich Menu 失敗：{str(e)}")
    
    return rich_menu_id

# 如果直接執行此文件，則設置 Rich Menu
if __name__ == "__main__":
    setup_rich_menu()