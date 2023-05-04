import logging
import requests

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response

sb = SkillBuilder()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def send_line(text):
    url ='https://notify-api.line.me/api/notify'
    token = "YOUR TOKEN HERE"
    headers ={'Authorization' : 'Bearer ' + token}
    message = text
    payload = {'message' : message}
    p = requests.post(url, headers=headers, data=payload)
    print(p)

@sb.request_handler(can_handle_func=is_request_type("LaunchRequest"))
def launch_request_handler(handler_input):
    speech = "何を買いますか"
    handler_input.response_builder.speak(speech).ask(speech)
    return handler_input.response_builder.response

@sb.request_handler(can_handle_func=is_intent_name("MyShoppingMemoIntent"))
def my_shopping_memo_handler(handler_input):
    slots = handler_input.request_envelope.request.intent.slots

    if "Item" in slots:
        item = slots["Item"].value
        speech = " {} ですね。ラインに記録します".format(item)
        send_line(item)
        handler_input.response_builder.set_should_end_session(True)
    else:
        speech = "商品がわかりませんでした。もう一度お願いします。"
        handler_input.response_builder.ask(speech)

    handler_input.response_builder.speak(speech)
    return handler_input.response_builder.response

@sb.exception_handler(can_handle_func=lambda i, e: True)
def all_exception_handler(handler_input, exception):
    print("Encountered following exception: {}".format(exception))

    speech = "すみません、問題が発生しました。もう一度お試しください。"
    handler_input.response_builder.speak(speech).ask(speech)
    handler_input.response_builder.set_should_end_session(True)

    return handler_input.response_builder.response

lambda_handler = sb.lambda_handler()
