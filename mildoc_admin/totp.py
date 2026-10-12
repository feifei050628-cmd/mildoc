import pyotp
import qrcode
import os
from loguru import logger
from dotenv import load_dotenv
load_dotenv()

ADMIN_TOTP_SECRET = os.getenv('ADMIN_TOTP_SECRET')

# 创建TOTP对象
totp = pyotp.TOTP(ADMIN_TOTP_SECRET)


def verify_totp(user_code):
    if not totp:
        logger.error("TOTP 未初始化")
        return False
    if not user_code:
        logger.error("验证码不能为空")
        return False
    return totp.verify(user_code)


def generate_totp_image(name: str, issuer_name: str):
    uri = totp.provisioning_uri(name=name, issuer_name=issuer_name)
    qr = qrcode.make(uri)
    qr.get_image().save("totp_qr.png")

if __name__ == "__main__":
   #generate_totp_image(name="jianzhang@mildoc.com", issuer_name="mildoc")
   input_code = input("请输入验证码: ")
   if verify_totp(input_code):
      print("验证成功")
   else:
      print("验证失败")