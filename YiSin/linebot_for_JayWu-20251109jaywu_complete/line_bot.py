from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler, LineBotApi
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import json
import random
import string
from datetime import datetime, timedelta
import urllib.parse
from util.address import *
from util.image import *


from dotenv import load_dotenv
import os
from db import *
from imagemap import create_identity_imagemap

load_dotenv()
sync_json_to_db()

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))


handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

IMAGE_NAME = "https://file.vidhubfile.com/imgtok/post/zTzZvHU/f_004.png"

IMAGE_BIRTHDAY = "https://file.vidhubfile.com/imgtok/post/L2DT2YY/f_001.png"

IMAGE_PHONE = "https://file.vidhubfile.com/imgtok/post/zTzZvHU/f_006.png"

IMAGE_ADDR = "https://file.vidhubfile.com/imgtok/post/zTzZvHU/f_005.png"

IMAGE_EMAIL = "https://file.vidhubfile.com/imgtok/post/rbRrHKw/f_001.png"

# Google 表單的基礎 URL
GOOGLE_FORM_BASE_URL = "https://docs.google.com/forms/d/e/1FAIpQLSe_eMdAWSUVn7Ze6ZgF5F5aL3Dt2c4pEQGzZBzqFmuOp40EvQ/viewform"

# Google 表單的欄位 ID
USER_ID_ID = "entry.1404949375"
ADDRESS_FIELD_ID = "entry.1219801190"
NAME_FIELD_ID = "entry.1742058975"
PHONE_FIELD_ID = "entry.1168269233"
EMAIL_FIELD_ID = "entry.83825998"
HANDOVER_DATE_FIELD_ID = "entry.858739430"     # 替換為交屋日期欄位ID

# 使用者的切換選單 ID
RICH_MENU_GENERAL_ID = "rm-general-xxxxxx"
RICH_MENU_RESIDENT_ID = "rm-resident-yyyyyy"
RICH_MENU_PRESELL_ID = "rm-presell-zzzzzz"

# TBD 
# address 選擇清單的函式化
# 切換選單 ID 功能

def get_current_date():
    return datetime.now().strftime('%Y-%m-%d')

def switch_rich_menu(user_id, rich_menu_id):
    """呼叫 Line API 變更使用者當前的 Rich Menu"""
    try:
        line_bot_api.link_rich_menu_to_user(user_id, rich_menu_id)
        # return True
    except Exception as e:
        print(f"Failed to switch Rich Menu for {user_id} to {rich_menu_id}: {e}")
        # return False
    

# 建立身份選擇的 Quick Reply 按鈕
def create_identity_quick_reply():
    quick_reply = QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(label="我是住戶", text="我是住戶")
            ),
            QuickReplyButton(
                action=MessageAction(label="我是訪客", text="我是訪客")
            )
        ]
    )
    return quick_reply

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    
    # 不管是否為新使用者，都直接添加到資料庫（避免重複）
    if not user_exists(user_id):
        add_user(user_id)
    
    # 添加 Quick Reply
    quick_reply = create_identity_quick_reply()
    text_message = TextSendMessage(
        text="請選擇您的身份：",
        quick_reply=quick_reply
    )
    
    # 移除 imagemap，只發送帶有 Quick Reply 的文字訊息
    line_bot_api.reply_message(event.reply_token, text_message)

# ----------------------------------------------------
# 處理 Rich Menu 頁籤切換邏輯
# ----------------------------------------------------
@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    postback_data = event.postback.data
    
    if postback_data.startswith('action=switch_menu'):
        params = dict(urllib.parse.parse_qsl(postback_data))
        target = params.get('target')
        
        target_id = None
        target_menu_name = ""
        
        if target == 'general':
            target_id = RICH_MENU_GENERAL_ID
            target_menu_name = "通用功能"
        elif target == 'resident':
            target_id = RICH_MENU_RESIDENT_ID
            target_menu_name = "住戶功能"
        elif target == 'presell':
            target_id = RICH_MENU_PRESELL_ID
            target_menu_name = "預售屋專區"
        
        if target_id:
            switched = switch_rich_menu(user_id, target_id)
            
            if not switched:
                # 切換失敗時發送訊息提醒用戶
                 line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"選單切換失敗，請聯繫客服。"))
        
        return

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id

    # 第一次來的使用者
    if not user_exists(user_id):
        add_user(user_id)

        # 添加 Quick Reply
        quick_reply = create_identity_quick_reply()
        text_message = TextSendMessage(
            text="請選擇您的身份：",
            quick_reply=quick_reply
        )
        line_bot_api.reply_message(event.reply_token, [text_message]) 
        return

    # 其他訊息處理（身份選擇後）
    msg = event.message.text
    user = get_user(user_id)

    if not user['identity']:
        if msg in ['我是訪客', '我是住戶']:

            update_identity(user_id, msg[-2:])

            # 無論住戶或訪客，都直接進入 ask_name 步驟
            update_user_step(user_id, 'ask_name')
            update_user_mode(user_id, 'initial_fill')
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"你選擇的身分是：{msg[-2:]}\n請輸入您的名字：")
            )
        else:
            # 添加 Quick Reply
            quick_reply = create_identity_quick_reply()
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="請先選擇身分喔！",
                    quick_reply=quick_reply  # 添加這個參數
                )
            )


    # 如果已經選擇身分，進行多輪提問，取得對方資訊
    if user['identity']:
        step = user['step']
        mode = user['mode']

        # 新增「確認交屋」功能
        # 新增「確認交屋」功能
        if msg == '確認交屋':
            # 檢查使用者是否有綁定戶別
            addresses = user.get('addresses', [])
            
            if not addresses:
                line_bot_api.reply_message(
                    event.reply_token, 
                    TextSendMessage(text="您目前沒有綁定的戶別，請先新增戶別。")
                )
                return
            
            # 修改：先顯示警告信息並提供確認/取消選項
            confirm_template = TemplateSendMessage(
                alt_text='確認交屋警告',
                template=ConfirmTemplate(
                    text="點選確認按鈕則確定該戶別保固起算日且無法更改!",
                    actions=[
                        MessageAction(label='確認', text='確認交屋步驟'),
                        MessageAction(label='取消', text='取消交屋')
                    ]
                )
            )
            
            # 使用較短的 step 名稱
            update_user_step(user_id, 'confirm_ho')  # 縮短名稱
            line_bot_api.reply_message(event.reply_token, confirm_template)
            return

        # 新增處理確認交屋警告的回應，使用較短的 step 名稱
        elif step == 'confirm_ho':  # 縮短名稱
            if msg == '確認交屋步驟':
                # 繼續交屋流程，顯示戶別選擇
                addresses = user.get('addresses', [])
                
                # 建立戶別選擇卡片
                carousel_columns = []
                for addr in addresses:
                    actions = [
                        MessageAction(
                            label="選擇此戶別交屋",
                            text=f"交屋戶別：{addr}"
                        )
                    ]
                    carousel_columns.append(
                        CarouselColumn(
                            title=addr,
                            text="請選擇要設定保固起算日的戶別：",
                            actions=actions
                        )
                    )
                    
                update_user_step(user_id, 'select_handover_addr')

                message = TemplateSendMessage(
                    alt_text="請選擇交屋戶別",
                    template=CarouselTemplate(columns=carousel_columns)
                )
                line_bot_api.reply_message(event.reply_token, message)
                return
            
            elif msg == '取消交屋':
                line_bot_api.reply_message(
                    event.reply_token, 
                    TextSendMessage(text="已取消交屋設定流程。")
                )
                update_user_step(user_id, None)  # 清除步驟狀態
                return
            
        # 處理交屋戶別選擇
        elif step == 'select_handover_addr' and msg.startswith('交屋戶別：'):
            selected_address = msg.replace('交屋戶別：', '')
            
            # 檢查該戶別是否已經有保固起算日
            address_info = get_address_info(selected_address)
            
            if address_info and address_info.get('warranty_start_date'):
                # 已有保固起算日，顯示信息
                warranty_date = address_info.get('warranty_start_date')
                reply_text = f"【{selected_address}】已於 {warranty_date} 設定為保固起算日，無法更改。\n\n"
                reply_text += "🔧保固期間：\n"
                reply_text += "．固定建材及設備部分(如門窗、粉刷、地磚等) 1 年期滿\n．不涉及結構之防水 2 年\n．結構保固 15 年"
                
                # 直接顯示文字訊息，移除表單選項
                line_bot_api.reply_message(
                    event.reply_token, 
                    TextSendMessage(text=reply_text)
                )
            else:
                # 設定新的保固起算日
                current_date_str = get_current_date()
                update_address_warranty_start_date(selected_address, current_date_str)
                
                reply_text = f"✅ 已成功設定【{selected_address}】的保固起算日為 {current_date_str}\n\n"
                reply_text += "🔧保固期間：\n"
                reply_text += "．固定建材及設備部分(如門窗、粉刷、地磚等) 1 年期滿\n．不涉及結構之防水 2 年\n．結構保固 15 年"
                
                # 直接顯示文字訊息，移除表單選項
                line_bot_api.reply_message(
                    event.reply_token, 
                    TextSendMessage(text=reply_text)
                )
            
            # 清除步驟狀態
            update_user_step(user_id, None)
            return
                    
        # 處理"私訊客服"按鈕 - 添加在這裡
        elif msg == '私訊客服':
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="🏠 請輸入您的問題，為確保客服能完整接收訊息，回覆前請暫勿點選其他按鈕 🙏")
            )
            return

            
        if msg == '我的個人資料':
            # 取得使用者所有資訊
            user_info = get_user(user_id)
            if user_info:
                # 取得戶別和密碼
                addresses = user_info.get('addresses', [])
                
                # 格式化戶別和密碼
                addresses_with_passwords = []
                if addresses:
                    for addr in addresses:
                        # 獲取戶別對應的密碼
                        address_info = get_address_info(addr)
                        password = address_info.get('password', '未知') if address_info else '未知'
                        addresses_with_passwords.append(f"{addr} -> {password}")
                    
                    addresses_text = '\n'.join(addresses_with_passwords)
                else:
                    addresses_text = "未設定"
                    
                profile_text = (
                    f"✅ 你的個人資料：\n"
                    f"身分：{user_info.get('identity', '未設定')}\n"
                    f"名字：{user_info.get('name', '未設定')}\n"
                    f"生日：{user_info.get('birthday', '未設定')}\n"
                    f"電話：{user_info.get('phone', '未設定')}\n"
                    f"Email：{user_info.get('email', '未設定')}\n"
                    f"戶別及密碼：\n{addresses_text}"
                )
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=profile_text)
                )
            return

        # 讓使用者修改個人資訊
        elif msg == "修改個人資訊":

            # 將 mode 更改，讓修改資訊過程不是預設的線性流程回答，而只更改單一欄位。
            update_user_mode(user_id, 'modify_data')
            
            message = TemplateSendMessage(
                alt_text="修改個人資訊",
                template=CarouselTemplate(
                    columns=[
                        CarouselColumn(
                            thumbnail_image_url = IMAGE_NAME,
                            title="名字",
                            text="修改名字",
                            actions=[
                                MessageAction(label="確認", text="修改_名字")
                            ]
                        ),
                        CarouselColumn(
                            thumbnail_image_url = IMAGE_BIRTHDAY,
                            title="生日",
                            text="修改生日",
                            actions=[
                                MessageAction(label="確認", text="修改_生日")
                            ]
                        ),
                        CarouselColumn(
                            thumbnail_image_url = IMAGE_PHONE,
                            title="電話",
                            text="修改電話",
                            actions=[
                                MessageAction(label="確認", text="修改_電話"),
                            ]
                        ),
                        CarouselColumn(
                            thumbnail_image_url = IMAGE_EMAIL,
                            title="Email",
                            text="修改 Email",
                            actions=[
                                MessageAction(label="確認", text="修改_Email"),
                            ]
                        ),
                        CarouselColumn(
                            thumbnail_image_url = IMAGE_ADDR,
                            title="建案",
                            text="新增建案",
                            actions=[
                                MessageAction(label="確認", text="修改_建案及戶別"),
                            ]
                        )
                    ]
                )
            )
            line_bot_api.reply_message(event.reply_token, message)
            return

        elif msg == '我的戶別密碼':
            # 取得使用者綁定的所有戶別，這部分是從你的資料庫讀取
            
            if not user['address']:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你目前沒有綁定的戶別。"))
                return
            
            # 將戶別字串轉換為列表，以便生成選單
            addresses = user['addresses']
            
            # 檢查戶別列表是否為空，理論上在上面已經處理過
            if not addresses:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你目前沒有綁定的戶別。"))
                return
            
            # 檢查戶別數量是否超過限制
            if len(addresses) > 10:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你綁定的戶別數量過多，請聯繫管理員。"))
                return

            carousel_columns = []
            for addr in addresses:
                # 建立每個戶別的 actions
                actions = [
                    MessageAction(
                        label="查詢密碼",
                        text=f"查詢密碼：{addr}"
                    ),
                    MessageAction(
                        label="重新生成密碼",
                        text=f"重新生成密碼：{addr}"
                    ),
                    MessageAction(
                        label="取消",
                        text="取消"
                    )
                ]

                # 建立一個新的 CarouselColumn，將戶別作為 title
                carousel_columns.append(
                    CarouselColumn(
                        title=addr,
                        text="請選擇操作：",
                        actions=actions
                    )
                )
                
            message = TemplateSendMessage(
                alt_text="請選擇戶別",
                template=CarouselTemplate(columns=carousel_columns)
            )
            line_bot_api.reply_message(event.reply_token, message)
            return

        # 處理查詢密碼
        elif msg.startswith('查詢密碼：'):
            # 從訊息中提取出完整的戶別
            selected_address = msg.replace('查詢密碼：', '')
            
            # 檢查該使用者是否確實綁定了這個戶別
            if selected_address not in user['addresses']:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="你沒有綁定這個戶別，無法查詢密碼。")
                )
                return

            # 從 JSON 檔案中查詢密碼
            address_info = get_address_info(selected_address)
            if address_info:
                reply_text = f"你的戶別【{selected_address}】的密碼是：{address_info['password']}"
            else:
                reply_text = "該戶別無密碼資訊，請聯繫管理員。"
            
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            return

        # 處理重新生成密碼
        elif msg.startswith('重新生成密碼：'):
            # 從訊息中提取出完整的戶別
            selected_address = msg.replace('重新生成密碼：', '')
            
            # 檢查該使用者是否確實綁定了這個戶別
            addresses_str = user.get('addresses', '')
            if selected_address not in user['addresses']:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="你沒有綁定這個戶別，無法重新生成密碼。")
                )
                return

            # 生成新的隨機密碼並更新 JSON 檔案
            new_password = generate_new_password()
            update_address_info(selected_address, new_password)
            
            reply_text = f"【{selected_address}】的新密碼是：{new_password}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            return
        
        elif msg.startswith("修改_"):

            # 戶名門牌用選擇的，故另外處理
            if msg == '修改_建案及戶別':
                update_user_mode(user_id, 'modify_data')
                update_user_step(user_id, 'ask_address_1')
                
                # 得到目前有的所有戶別資訊，並把它做成 column 回傳
                columns = create_addresses_select_columns()

                # 3. 建立選單訊息
                address_selection_msg = TemplateSendMessage(
                    alt_text='請選擇你的戶名或門牌',
                    template=CarouselTemplate(
                        columns=columns 
                    )
                )

                line_bot_api.reply_message(event.reply_token, address_selection_msg)
                return

            update_user_mode(user_id, 'modify_data')
            field_map = {
                "修改_名字": ("ask_name", "請輸入新的名字："),
                "修改_生日": ("ask_birthday", "請輸入新的生日（yyyy-mm-dd）："),
                "修改_電話": ("ask_phone", "請輸入新的電話號碼："),
                "修改_Email": ("ask_email", "請輸入新的 Email：")
            }
            step, question = field_map[msg]
            update_user_step(user_id, step)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=question))
            return

        elif msg == '我要報修':

            addresses = user.get('addresses', []) 
        
            # 篩選成屋戶別，剔除預售屋
            ready_property = [
                addr for addr in addresses if is_ready_property(addr)
            ]

            if not ready_property:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你目前沒有綁定的戶別，請先新增戶別。"))
                return
            
            if len(ready_property) > 10:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="你綁定的戶別數量過多，請聯繫管理員。"))
                return

            carousel_columns = []
            for addr in ready_property:
                actions = [
                    MessageAction(
                        label="選擇此戶別報修",
                        text=f"報修戶別：{addr}" 
                    )
                ]
                carousel_columns.append(
                    CarouselColumn(
                        title=addr,
                        text="請選擇要報修的戶別：",
                        actions=actions
                    )
                )
                
            update_user_step(user_id, 'select_repairAddr')

            message = TemplateSendMessage(
                alt_text="請選擇報修戶別",
                template=CarouselTemplate(columns=carousel_columns)
            )
            line_bot_api.reply_message(event.reply_token, message)
            return

        elif step == 'select_repairAddr' and msg.startswith('報修戶別：'):
            selected_address = msg.replace('報修戶別：', '')
            
            # 1. 執行保固查詢邏輯
            address_info = get_address_info(selected_address)
            warranty_start_date_str = address_info.get('warranty_start_date') if address_info else None
            
            reply_text = f"【{selected_address}】保固狀態檢查：\n"
            warranty_status = "UNKNOWN"

            if not warranty_start_date_str:
                reply_text += "🔴 **查無保固紀錄。**\n此戶別可能尚未設定保固起算日，請先執行「確認交屋」。"
                warranty_status = "NO_RECORD"
            else:
                try:
                    # 提供保固資訊
                    start_date = datetime.strptime(warranty_start_date_str, '%Y-%m-%d').date()

                    reply_text += f"\n保固起算日：{start_date.strftime('%Y-%m-%d')}\n\n"
                    reply_text += "🔧保固期間：\n"
                    reply_text += "．固定建材及設備部分(如門窗、粉刷、地磚等) 1 年期滿\n．不涉及結構之防水 2 年\n．結構保固 15 年"
                    reply_text += "保固期滿可繼續提供檢查修繕之服務，費用須由客戶承擔！"

                except ValueError:
                    reply_text += "🔴 系統紀錄日期格式錯誤，請聯繫管理員。"
                    warranty_status = "ERROR"

            # 2. 將戶別暫存，並進入確認步驟
            update_temp_value(user_id, selected_address)
            update_user_step(user_id, 'confirm_warranty')
            
            # 3. 建立確認訊息
            confirm_msg = TemplateSendMessage(
                alt_text='請確認是否繼續報修',
                template=ConfirmTemplate(
                    text=f"{reply_text}\n\n您是否要針對此戶別繼續進行報修？",
                    actions=[
                        MessageAction(label='✅ 繼續報修', text='確認繼續報修'),
                        MessageAction(label='❌ 取消報修', text='取消報修')
                    ]
                )
            )
            line_bot_api.reply_message(event.reply_token, confirm_msg)
            return

        elif step == 'confirm_warranty':
            selected_address = user['temp_value']

            if msg == '確認繼續報修':

                # 獲取戶別信息以獲取保固起算日（交屋日期）
                address_info = get_address_info(selected_address)
                warranty_date = address_info.get('warranty_start_date') if address_info else get_current_date()

                # 準備預填資料
                user_id = user.get('line_user_id', '錯誤')
                user_name = user.get('name', '未提供姓名')
                user_phone = user.get('phone', '未提供電話')
                user_email = user.get('email', '未提供 Email')
                
                # --- 開始生成 Google 表單連結 ---
                
                # 進行 URL 編碼
                encoded_address = urllib.parse.quote_plus(selected_address)
                encoded_name = urllib.parse.quote_plus(user_name)
                encoded_phone = urllib.parse.quote_plus(user_phone)
                encoded_email = urllib.parse.quote_plus(user_email)
                encoded_date = urllib.parse.quote_plus(warranty_date)
                encoded_id = urllib.parse.quote_plus(str(user_id))
                
                # 組合預填連結
                prefilled_url = (
                    f"{GOOGLE_FORM_BASE_URL}?usp=pp_url"
                    f"&{USER_ID_ID}={encoded_id}"
                    f"&{ADDRESS_FIELD_ID}={encoded_address}"
                    f"&{NAME_FIELD_ID}={encoded_name}"
                    f"&{PHONE_FIELD_ID}={encoded_phone}"
                    f"&{EMAIL_FIELD_ID}={encoded_email}"
                    f"&{HANDOVER_DATE_FIELD_ID}={encoded_date}"
                )

                # 生成按鈕訊息，導向 Google 表單
                reply_msg = TemplateSendMessage(
                    alt_text='報修確認',
                    template=ButtonsTemplate(
                        title=f'已選擇戶別：{selected_address}',
                        text='請點擊按鈕前往 Google 表單，填寫報修內容並完成送出。',
                        actions=[
                            URIAction(label='前往 Google 表單', uri=prefilled_url)
                        ]
                    )
                )
                
                line_bot_api.reply_message(event.reply_token, reply_msg)

            elif msg == '取消報修':
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 報修流程已取消。"))

            # 清理狀態
            clear_temp_value(user_id)
            update_user_step(user_id, None)
            return

        elif msg == '確認':

            # 如果使用者是修改資料，mode 會是 modify_data，則不繼續進行提問
            if mode == 'modify_data':

                # 戶別額外詢問
                if step == 'ask_address':
                    full_address = user['temp_value']
                    try:
                        with open('available_addresses.json', 'r+', encoding='utf-8') as f:
                            available_addresses = json.load(f)

                            # 檢查完整的戶別是否存在於列表中
                            address_exists = any(item["address"] == full_address for item in available_addresses)

                            if address_exists:
                                # 如果戶別存在，將完整戶別暫存，並進入下一步驟詢問密碼
                                update_temp_value(user_id, full_address)
                                update_user_step(user_id, 'ask_password')
                                
                                line_bot_api.reply_message(
                                    event.reply_token,
                                    TextSendMessage(text="請輸入該戶別的綁定密碼：")
                                )
                            else:
                                # 如果戶別不存在，給予錯誤提示，並讓使用者重填
                                line_bot_api.reply_message(
                                    event.reply_token,
                                    TextSendMessage(text="此戶別不存在")
                                )
                                clear_temp_value(user_id)
                                update_user_step(user_id, None)

                    except FileNotFoundError:
                        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="戶別清單檔案不存在，請聯繫管理員。"))
                        clear_temp_value(user_id)
                        update_user_step(user_id, None)
                    return

                else:
                    update_user_field(user_id, step[4:], user['temp_value'])
                    update_user_step(user_id, None)
                    clear_user_mode(user_id)
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 資料修改完畢，謝謝你的配合！"))
                    return

            if step == 'ask_id_number':
                update_user_field(user_id, 'id_number', user['temp_value'])
                clear_temp_value(user_id)
                update_user_step(user_id, 'ask_name')
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入你的名字"))
                return

            elif step == 'ask_name':
                update_user_field(user_id, 'name', user['temp_value'])
                clear_temp_value(user_id)
                update_user_step(user_id, 'ask_birthday')
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入你的生日（格式 yyyy-mm-dd）："))
                return

            elif step == 'ask_birthday':
                update_user_field(user_id, 'birthday', user['temp_value'])
                clear_temp_value(user_id)
                update_user_step(user_id, 'ask_phone')
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入你的電話號碼："))
                return

            elif step == 'ask_phone':
                update_user_field(user_id, 'phone', user['temp_value'])
                clear_temp_value(user_id)
                update_user_step(user_id, 'ask_email')
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入你的 Email："))
                return

            elif step == 'ask_email':
                update_user_field(user_id, 'email', user['temp_value'])
                clear_temp_value(user_id)

                if user['identity'] == "訪客":
                    # 訪客跳過戶別填寫，清空訪客填寫 step
                    clear_user_mode(user_id)
                    update_user_step(user_id, None)

                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="已完成資料填寫！"))
                    return

                else :
                    # 住戶需要先綁定戶別
                    update_user_step(user_id, 'ask_address_1')
                    
                    # 得到目前有的所有戶別資訊，並把它做成 column 回傳
                    columns = create_addresses_select_columns()

                    # 3. 建立選單訊息
                    text_message = TextSendMessage(text='請選擇你的案名')

                    address_selection_msg = TemplateSendMessage(
                        alt_text='請選擇你的案名',
                        template=CarouselTemplate(
                            columns=columns 
                        )
                    )

                    line_bot_api.reply_message(event.reply_token, [text_message, address_selection_msg])

                    return

            elif step == 'ask_address':
                user = get_user(user_id)

                full_address = user['temp_value']

                try:
                    with open('available_addresses.json', 'r', encoding='utf-8') as f:
                        available_addresses = json.load(f)

                    # 檢查完整的戶別是否存在於列表中
                    address_exists = any(item["address"] == full_address for item in available_addresses)

                    if address_exists:
                        # 如果戶別存在，將完整戶別暫存，並進入下一步驟詢問密碼
                        update_temp_value(user_id, full_address)
                        update_user_step(user_id, 'ask_password')
                        
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text="請輸入該戶的綁定密碼：")
                        )
                    else:
                        # 如果戶別不存在，給予錯誤提示，並讓使用者重填
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text="此戶不存在，請確認後重新輸入戶別")
                        )
                        clear_temp_value(user_id)
                        update_user_step(user_id, None)

                except FileNotFoundError:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="戶別清單檔案不存在，請聯繫管理員。"))
                    clear_temp_value(user_id)
                    update_user_step(user_id, None)
                return

        elif msg == '重填':
            if step in ['ask_name', 'ask_birthday', 'ask_phone', 'ask_email']:
                clear_temp_value(user_id)
                question = {
                    'ask_name': "請重新輸入你的名字：",
                    'ask_birthday': "請重新輸入你的生日（格式 yyyy-mm-dd）：",
                    'ask_phone': "請重新輸入你的電話號碼：",
                    'ask_email': "請重新輸入你的 Email：",
                }
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=question[step]))
                return
            elif step == 'ask_address':
                update_user_step(user_id, "ask_address_1")
                with open('addresses.json', 'r', encoding='utf-8') as f:
                    addresses = json.load(f)

                # 將戶別轉換為 ButtonTemplate 的 actions
                actions = [
                    MessageAction(
                        label=addr,
                        text=addr
                    ) for addr in addresses
                ]
                address_selection_msg = TemplateSendMessage(
                    alt_text='請選擇你的案名及戶別',
                    template=ButtonsTemplate(
                        title='請選擇你的案名及戶別',
                        text='請從以下選項中選擇你的案名：',
                        actions=actions
                    )
                )
                line_bot_api.reply_message(event.reply_token, address_selection_msg)
                return

        # 新增戶別的密碼
        elif step == "ask_password":
            entered_password = msg
            full_address = user['temp_value']
            
            try:
                with open('available_addresses.json', 'r', encoding='utf-8') as f:
                    available_addresses = json.load(f)

                # 找到對應戶別的密碼
                correct_password = None
                for item in available_addresses:
                    if item["address"] == full_address:
                        correct_password = item["password"]
                        break
                
                if correct_password and correct_password == entered_password:
                    # 密碼正確，戶別新增成功
                    append_address(user_id, full_address)
                    
                    # 新增後更改密碼
                    new_password = generate_new_password()
                    update_address_info(full_address, new_password)
                    
                    reply_text = f"✅ 該戶別已成功新增！\n您戶別【{full_address}】的新密碼是：{new_password}(密碼於[我的資料]可以查看)"

                    # 如果訪客新增戶別，則自動將他的身分變成住戶
                    if user['identity'] == "訪客":
                        update_user_field(user_id, 'identity', '住戶')

                    # 清理狀態
                    clear_temp_value(user_id)
                    update_user_step(user_id, None)
                    
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
                else:
                    if mode != 'modify_data':
                        update_user_field(user_id, 'identity', '訪客')
                    clear_temp_value(user_id)
                    update_user_step(user_id, None)

                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="密碼錯誤，請於「修改個人資料」中再新增一次。")
                    )
                    
            except FileNotFoundError:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="戶別清單檔案不存在，請聯繫管理員。")
                )
            return

        elif step == 'ask_id_number':
            update_temp_value(user_id, msg)
            reply_text = f"您輸入的身分證字號是：{msg}，正確嗎？"
            confirm_msg = TemplateSendMessage(
                alt_text='請確認身分證字號',
                template=ConfirmTemplate(
                    text=reply_text,
                    actions=[
                        MessageAction(label='✅ 正確', text='確認'),
                        MessageAction(label='🔁 重填', text='重填')
                    ]
                )
            )
            line_bot_api.reply_message(event.reply_token, confirm_msg)
            return

        elif step == 'ask_name':
            update_temp_value(user_id, msg)
            reply_text = f"您輸入的名字是：{msg}，正確嗎？"
            confirm_msg = TemplateSendMessage(
                alt_text='請確認名字',
                template=ConfirmTemplate(
                    text=reply_text,
                    actions=[
                        MessageAction(label='✅ 正確', text='確認'),
                        MessageAction(label='🔁 重填', text='重填')
                    ]
                )
            )
            line_bot_api.reply_message(event.reply_token, confirm_msg)
            return

        elif step == 'ask_birthday':
            update_temp_value(user_id, msg)
            reply_text = f"您輸入的生日是：{msg}，正確嗎？"
            confirm_msg = TemplateSendMessage(
                alt_text='請確認生日',
                template=ConfirmTemplate(
                    text=reply_text,
                    actions=[
                        MessageAction(label='✅ 正確', text='確認'),
                        MessageAction(label='🔁 重填', text='重填')
                    ]
                )
            )
            line_bot_api.reply_message(event.reply_token, confirm_msg)
            return

        elif step == 'ask_phone':
            update_temp_value(user_id, msg)
            reply_text = f"您輸入的電話號碼是：{msg}，正確嗎？"
            confirm_msg = TemplateSendMessage(
                alt_text='請確認電話號碼',
                template=ConfirmTemplate(
                    text=reply_text,
                    actions=[
                        MessageAction(label='✅ 正確', text='確認'),
                        MessageAction(label='🔁 重填', text='重填')
                    ]
                )
            )
            line_bot_api.reply_message(event.reply_token, confirm_msg)
            return

        elif step == 'ask_email':
            update_temp_value(user_id, msg)
            reply_text = f"您輸入的 Email 是：{msg}，正確嗎？"
            confirm_msg = TemplateSendMessage(
                alt_text='請確認 Email',
                template=ConfirmTemplate(
                    text=reply_text,
                    actions=[
                        MessageAction(label='✅ 正確', text='確認'),
                        MessageAction(label='🔁 重填', text='重填')
                    ]
                )
            )
            line_bot_api.reply_message(event.reply_token, confirm_msg)
            return

        # 在使用者想要新增戶名時，先產生選單給使用者選擇
        # 順序 ask_address_1 -> ask_address
        elif step == 'ask_address_1':
            update_temp_value(user_id, msg)
            reply_text = f"您選擇的案名是：{msg}，請輸入戶別:\n（例：3樓A戶的住戶請發送3A，依此類推!）"
            update_user_step(user_id, 'ask_address')
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            return

        elif step == 'ask_address':
            # 將輸入轉為大寫，方便後續統一比對
            unit_input = msg.upper()  
            full_address = f"{user['temp_value']}_{unit_input}"
    
            # 檢查戶別是否存在，但先不刪除
            try:
                with open('available_addresses.json', 'r', encoding='utf-8') as f:
                    available_addresses = json.load(f)

                    # 不區分大小寫比較戶別
                    address_exists = False
                    matching_address = None
                    
                    for item in available_addresses:
                        # 獲取戶別中的戶別部分（案名_戶別 格式）
                        parts = item["address"].split('_')
                        if len(parts) == 2:
                            case_name, unit = parts
                            # 檢查案名是否匹配，並忽略戶別大小寫
                            if case_name == user['temp_value'] and unit.upper() == unit_input:
                                address_exists = True
                                matching_address = item["address"]  # 使用資料庫中的原始格式
                                break
                    
                    if address_exists and matching_address:
                        # 戶別存在，將完整戶別暫存（使用資料庫中的原始格式）
                        update_temp_value(user_id, matching_address)
                        
                        reply_text = f"您輸入的案名及戶別是：{matching_address}，正確嗎？"
                        confirm_msg = TemplateSendMessage(
                            alt_text='請確認戶名或門牌',
                            template=ConfirmTemplate(
                                text=reply_text,
                                actions=[
                                    MessageAction(label='✅ 正確', text='確認'),
                                    MessageAction(label='🔁 重填', text='重填')
                                ]
                            )
                        )
                        line_bot_api.reply_message(event.reply_token, confirm_msg)

                    else:
                        # 讓使用者停在這個狀態，可以一直輸入戶名
                        update_user_step(user_id, 'ask_address')
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text="此戶別不存在，請確認後再試一次。\n（例：3樓A戶的住戶請發送3A，依此類推）")
                        )
                        
            except FileNotFoundError:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="地址清單檔案不存在，請聯繫管理員。")
                )
            return
        # 在 handle_message 函數中添加新的處理分支
        elif msg == '管理員':
            # 設置下一步驟為管理員密碼驗證
            update_user_step(user_id, 'admin_password_auth')
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="請輸入管理員密碼：")
            )
            return

        # 處理管理員密碼驗證
        elif step == 'admin_password_auth':
            admin_password = os.getenv("ADMIN_PASSWORD", "yisin1234")  # 預設密碼，應該從環境變量獲取
            
            if msg == admin_password:
                # 密碼正確，獲取所有戶別資訊
                try:
                    with open('available_addresses.json', 'r', encoding='utf-8') as f:
                        available_addresses = json.load(f)
                    
                    # 格式化所有戶別及密碼
                    addresses_info = []
                    for item in available_addresses:
                        address = item.get("address", "")
                        password = item.get("password", "")
                        if address and password:
                            addresses_info.append(f"【{address}】密碼: {password}")
                    
                    if addresses_info:
                        # 分批發送，避免訊息太長
                        batch_size = 10
                        for i in range(0, len(addresses_info), batch_size):
                            batch = addresses_info[i:i+batch_size]
                            reply_text = "\n".join(batch)
                            
                            # 只對第一批使用 reply_token，後續批次使用 push_message
                            if i == 0:
                                line_bot_api.reply_message(
                                    event.reply_token,
                                    TextSendMessage(text=f"所有戶別密碼：\n{reply_text}")
                                )
                            else:
                                line_bot_api.push_message(
                                    user_id,
                                    TextSendMessage(text=reply_text)
                                )
                    else:
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text="沒有找到任何戶別資訊。")
                        )
                except FileNotFoundError:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="戶別清單檔案不存在，請聯繫系統管理員。")
                    )
                
                # 清除步驟狀態
                update_user_step(user_id, None)
            else:
                # 密碼錯誤
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="管理員密碼錯誤，請聯繫系統管理員。")
                )
                # 清除步驟狀態
                update_user_step(user_id, None)
            return
        


    # 雖然不期望他們選擇訪客，但還是做一下
    elif user['identity'] == '訪客':
        if msg == '我要報修':
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請先輸入身分才能報修喔"))
            return

if __name__ == "__main__":
    try:
        print("正在同步戶別資料到資料庫...")
        from db import sync_json_to_db, load_addresses_data
        addresses_data = load_addresses_data()
        print(f"JSON檔案中有 {len(addresses_data)} 筆戶別資料")
        if sync_json_to_db():
            print("資料已成功同步到資料庫")
        else:
            print("資料同步失敗，請檢查日誌")
    except Exception as e:
        print(f"同步過程出錯: {e}")
    app.run(port=3000)



# https://docs.google.com/forms/d/e/1FAIpQLSe_eMdAWSUVn7Ze6ZgF5F5aL3Dt2c4pEQGzZBzqFmuOp40EvQ/viewform?usp=pp_url&entry.1742058975=%E9%99%B3%E5%BA%A0%E5%AE%87&entry.1219801190=%E6%96%B0%E7%AB%B9%E5%B8%82%E6%98%8E%E6%B9%96%E8%B7%AF&entry.1168269233=0963656329&entry.83825998=shine.u.chen@gmail.com