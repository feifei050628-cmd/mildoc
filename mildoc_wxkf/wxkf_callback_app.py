import os
import xml.etree.ElementTree as ET
from flask import Flask, request, abort
from WXBizMsgCrypt import WXBizMsgCrypt
from cursor_manager import save_token
from loguru import logger
import os
from dotenv import load_dotenv

load_dotenv()

WECOM_CORP_ID=os.getenv('WECOM_CORP_ID')
WECOM_TOKEN=os.getenv('WECOM_TOKEN')
WECOM_ENCODING_AES_KEY=os.getenv('WECOM_ENCODING_AES_KEY')


# 创建Flask应用
app = Flask("mildoc_wxkf")



def get_wxcrypt():
    """
    获取企业微信加解密工具对象
    """
    return WXBizMsgCrypt(WECOM_TOKEN, WECOM_ENCODING_AES_KEY, WECOM_CORP_ID)


@app.route('/callback/command', methods=['GET'])
def wecom_callback_get():
    """
    企业微信回调接口
    GET请求：用于验证回调URL的有效性
    """

    logger.info("wecom_callback_get请求被调用")

    # 获取加解密工具对象
    wxcrypt = get_wxcrypt()
    
    # 获取URL参数
    msg_signature = request.args.get('msg_signature', '')
    timestamp = request.args.get('timestamp', '')
    nonce = request.args.get('nonce', '')
    echostr = request.args.get('echostr', '')
    
    logger.info(f"收到回调请求 - Method: {request.method}, msg_signature: {msg_signature}, timestamp: {timestamp}, nonce: {nonce}, echostr: {echostr}")
    # URL验证
    
    if not all([msg_signature, timestamp, nonce, echostr]):
        logger.error("GET请求缺少必要参数")
        abort(400)
    
    try:
        
        # 验证URL并解密echostr
        ret_code, decrypt_echostr = wxcrypt.VerifyURL(msg_signature, timestamp, nonce, echostr)
        
        logger.info(f"验证URL结果: {ret_code}, decrypt_echostr: {decrypt_echostr}")

        if ret_code == 0:
            return decrypt_echostr
        if ret_code == -40001:
            logger.error("签名验证失败 - 请检查Token配置是否与企业微信后台一致")
            abort(403)
        if ret_code == -40002:
            logger.error("AES解密失败或CorpID不匹配 - 请检查EncodingAESKey和CorpID配置")
            abort(403)
        
        logger.error(f"未知错误码: {ret_code}")
        abort(500)
    except Exception as e:
        logger.error(f"URL验证过程发生错误: {str(e)}")
        abort(500)
        
    



@app.route('/callback/command', methods=['POST'])
def wecom_callback_post():
    """
    企业微信回调接口
    POST请求：接收企业微信推送的消息和事件
    """

    logger.info("wecom_callback_post请求被调用")
    
    # 获取加解密工具对象
    wxcrypt = get_wxcrypt()
    
    # 获取URL参数
    msg_signature = request.args.get('msg_signature', '')
    timestamp = request.args.get('timestamp', '')
    nonce = request.args.get('nonce', '')
    
    logger.info(f"收到回调请求 - Method: {request.method}, msg_signature: {msg_signature}, timestamp: {timestamp}, nonce: {nonce}")
    
    # 接收消息
    if not all([msg_signature, timestamp, nonce]):
        logger.error("POST请求缺少必要参数")
        abort(400)
        
    try:
        # 获取POST数据
        post_data = request.get_data(as_text=True)

                
        # 解密消息
        ret, msg = wxcrypt.DecryptMsg(post_data, msg_signature, timestamp, nonce)
        
        if ret != 0:
            logger.error(f"消息解密失败，错误码: {ret}")
            abort(403)
        
        logger.info(f"消息解密成功: {msg}")
        
        # 解析XML消息
        root = ET.fromstring(msg)
        msg_type = root.find('MsgType').text

        if msg_type != 'event':
            logger.info(f"收到非客服事件消息，跳过处理 - msg_type: {msg_type}")
            return "success"

        event = root.find('Event').text

        if event != 'kf_msg_or_event':
            logger.info(f"收到非客服事件消息，跳过处理 - event: {event}")
            return "success"

        # 微信客服消息或事件
        logger.info("收到微信客服事件，开始处理客服消息")
        
        # 获取Token和OpenKfId
        token = root.find('Token').text if root.find('Token') is not None else ''
        open_kfid = root.find('OpenKfId').text if root.find('OpenKfId') is not None else ''
        
        logger.info(f"token: {token}, open_kfid: {open_kfid}")
        if token and open_kfid:
            save_token(open_kfid, token)
            return "success"
        else:
            logger.error("客服事件缺少必要参数 - Token或OpenKfId为空")
            return "success"
        
    except Exception as e:
        logger.error(f"处理POST请求时发生错误: {str(e)}")
        abort(500)



@app.route('/', methods=['GET'])
def index():
    logger.info("index请求被调用")
    return '''
    <h1>企业微信回调服务</h1>
    <p>服务正在运行...</p>'''



if __name__ == '__main__':
    # 检查配置
    logger.info("企业微信回调服务启动中...")
    logger.info(f"企业ID: {WECOM_CORP_ID}")
    logger.info(f"Token: {WECOM_TOKEN[:10]}..." if WECOM_TOKEN else "Token: 未配置")
    logger.info(f"EncodingAESKey: {WECOM_ENCODING_AES_KEY[:10]}..." if WECOM_ENCODING_AES_KEY else "EncodingAESKey: 未配置")

    # 启动服务
    app.run(host='0.0.0.0', port=8891, debug=True, threaded=True, processes=1) 