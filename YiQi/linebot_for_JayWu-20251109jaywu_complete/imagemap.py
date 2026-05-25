from linebot.models import ImagemapSendMessage, BaseSize, URIImagemapAction, MessageImagemapAction, ImagemapArea
from util.image import *

def create_identity_imagemap():
    return ImagemapSendMessage(
        base_url = IMAGE_IDENTITY,  # 你的 imagemap 圖片網址（需含無副檔名 base url）
        alt_text = '請選擇你的身分',
        base_size = BaseSize(height=1040, width=1040),
        actions=[
            MessageImagemapAction(
                text='我是住戶',
                area=ImagemapArea(x=0, y=0, width=520, height=1040)
            ),
            MessageImagemapAction(
                text='我是訪客',
                area=ImagemapArea(x=520, y=0, width=520, height=1040)
            )
        ]
    )
