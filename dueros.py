import json, math, time
import logging

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (MAJOR_VERSION, MINOR_VERSION)
from homeassistant.auth.const import ACCESS_TOKEN_EXPIRATION
import homeassistant.util.color as color_util
import homeassistant.auth.models as models
from typing import Optional
from datetime import timedelta
from homeassistant.helpers.state import AsyncTrackStates
from urllib.request import urlopen
_LOGGER = logging.getLogger(__name__)

MAIN = 'dueros'

EXPIRE_HOURS = 'expire_hours'
DOMAIN       = 'dueros'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(EXPIRE_HOURS): cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)

_hass         = None
_expire_hours = None

async def async_create_refresh_token77(
        user: models.User, client_id: Optional[str] = None) \
        -> models.RefreshToken:
    """Create a new token for a user."""
    _LOGGER.info('access token expiration: %d hours', _expire_hours)
    refresh_token = models.RefreshToken(user=user, 
                                        client_id=client_id,
                                        access_token_expiration = timedelta(hours=_expire_hours))
    user.refresh_tokens[refresh_token.id] = refresh_token
    _hass.auth._store._async_schedule_save()
    return refresh_token

async def async_create_refresh_token78(
        user: models.User, client_id: Optional[str] = None,
        client_name: Optional[str] = None,
        client_icon: Optional[str] = None,
        token_type: str = models.TOKEN_TYPE_NORMAL,
        access_token_expiration: timedelta = ACCESS_TOKEN_EXPIRATION) \
        -> models.RefreshToken:
    if access_token_expiration == ACCESS_TOKEN_EXPIRATION:
        access_token_expiration = timedelta(hours=_expire_hours)
    _LOGGER.info('Access token expiration: %d hours', _expire_hours)
    """Create a new token for a user."""
    kwargs = {
        'user': user,
        'client_id': client_id,
        'token_type': token_type,
        'access_token_expiration': access_token_expiration
    }  # type: Dict[str, Any]
    if client_name:
        kwargs['client_name'] = client_name
    if client_icon:
        kwargs['client_icon'] = client_icon

    refresh_token = models.RefreshToken(**kwargs)
    user.refresh_tokens[refresh_token.id] = refresh_token

    _hass.auth._store._async_schedule_save()
    return refresh_token

async def async_setup(hass, config):
    global _hass, _expire_hours
    _hass         = hass
    _expire_hours = config[DOMAIN].get(EXPIRE_HOURS)
    
    if _expire_hours is not None:
        if MAJOR_VERSION == 0 and MINOR_VERSION <= 77:
            _hass.auth._store.async_create_refresh_token = async_create_refresh_token77
        else:
            _hass.auth._store.async_create_refresh_token = async_create_refresh_token78
    _hass.http.register_view(DuerosGateView)

    return True

class DuerosGateView(HomeAssistantView):
    """View to handle Configuration requests."""

    url = '/dueros_gate'
    name = 'dueros_gate'
    requires_auth = False

    async def post(self, request):
        """Update state of entity."""
        try:
            data = await request.json()
            response = await handleRequest(data)
        except:
            import traceback
            _LOGGER.error(traceback.format_exc())
            response = {'header': {'name': 'errorResult'}, 'payload': errorResult('SERVICE_ERROR', 'service exception')}

        return self.json(response)

def errorResult(errorCode, messsage=None):
    """Generate error result"""
    messages = {
        'INVALIDATE_CONTROL_ORDER':    'invalidate control order',
        'SERVICE_ERROR': 'service error',
        'DEVICE_NOT_SUPPORT_FUNCTION': 'device not support',
        'INVALIDATE_PARAMS': 'invalidate params',
        'DEVICE_IS_NOT_EXIST': 'device is not exist',
        'IOT_DEVICE_OFFLINE': 'device is offline',
        'ACCESS_TOKEN_INVALIDATE': ' access_token is invalidate'
    }
    return {'errorCode': errorCode, 'message': messsage if messsage else messages[errorCode]}

async def handleRequest(data):
    """Handle request"""
    header = data['header']
    payload = data['payload']
    properties = None
    name = header['name']
    _LOGGER.info("Handle Request: %s", data)

    token = await _hass.auth.async_validate_access_token(payload['accessToken'])
    if token is not None:
        namespace = header['namespace']
        if namespace == 'DuerOS.ConnectedHome.Discovery':
            name = 'DiscoverAppliancesResponse'
            result = discoveryDevice()
        elif namespace == 'DuerOS.ConnectedHome.Control':
            result = await controlDevice(name, payload)
        elif namespace == 'DuerOS.ConnectedHome.Query':
            result = queryDevice(name, payload)
            if not 'errorCode' in result:
                properties = result
                result = {}
        else:
            result = errorResult('SERVICE_ERROR')
    else:
        result = errorResult('ACCESS_TOKEN_INVALIDATE')

    # Check error and fill response name
    header['name'] = name

    # Fill response deviceId
    if 'deviceId' in payload:
        result['deviceId'] = payload['deviceId']

    response = {'header': header, 'payload': result}
    if properties:
        response['properties'] = properties
    _LOGGER.info("Respnose: %s", response)
    return response

def discoveryDevice():

    states = _hass.states.async_all()
    # groups_ttributes = groupsAttributes(states)

    devices = []

    # devices.append({
    #     'applianceId': 'light.',
    #     'friendlyName': '小夜灯',
    #     'friendlyDescription': '小夜灯',
    #     'additionalApplianceDetails': [],
    #     'applianceTypes': ['LIGHT'],
    #     'isReachable': True,
    #     'manufacturerName': 'HomeAssistant',
    #     'modelName': 'HomeAssistantLight',
    #     'version': '1.0',
    #     'actions': ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff", "setBrightnessPercentage", "incrementBrightnessPercentage", "decrementBrightnessPercentage", "setColor"],
    # })
    for state in states:
        attributes = state.attributes

        if attributes.get('hidden') or attributes.get('dueros_hidden'):
            continue

        friendly_name = attributes.get('friendly_name')
        if friendly_name is None:
            continue

        entity_id = state.entity_id

        deviceTypes = guessDeviceType(entity_id, attributes)
        if deviceTypes is None:
            continue

        actions = guessAction(entity_id, attributes)

        devices.append({
            'applianceId': entity_id,
            'friendlyName': friendly_name,
            'friendlyDescription': friendly_name,
            'additionalApplianceDetails': [],
            'applianceTypes': deviceTypes,
            'isReachable': True,
            'manufacturerName': 'HomeAssistant',
            'modelName': 'HomeAssistantLight',
            'version': '1.0',
            'actions': actions,
            })

    #for sensor in devices:
        #if sensor['deviceType'] == 'sensor':
            #_LOGGER.info(json.dumps(sensor, indent=2, ensure_ascii=False))
    return {'discoveredAppliances': devices}

async def controlDevice(action, payload):
    applianceDic = payload['appliance']
    entity_id = applianceDic['applianceId']
    domain = entity_id[:entity_id.find('.')]
    data = {"entity_id": entity_id }
    if domain in TRANSLATIONS.keys():
        translation = TRANSLATIONS[domain][action]
        if callable(translation):
            service, content = translation(_hass.states.get(entity_id), payload)
            data.update(content)
        else:
            service = translation
    else:
        service = getControlService(action)

    _LOGGER.info(_hass.states.get(entity_id).attributes)
    with AsyncTrackStates(_hass) as changed_states:
        result = await _hass.services.async_call(domain, service, data, True)

    return {} if result else errorResult('IOT_DEVICE_OFFLINE')


def queryDevice(name, payload):
    deviceId = payload['deviceId']

    if payload['deviceType'] == 'sensor':

        states = _hass.states.async_all()

        entity_ids = []
        for state in states:
            attributes = state.attributes
            if state.entity_id.startswith('group.') and (attributes['friendly_name'] == deviceId or attributes.get('hagenie_zone') == deviceId):
                entity_ids = attributes.get('entity_id')
                break

        properties = [{'name':'powerstate', 'value':'on'}]
        for state in states:
            entity_id = state.entity_id
            attributes = state.attributes
            if entity_id.startswith('sensor.') and (entity_id in entity_ids or attributes['friendly_name'].startswith(deviceId) or attributes.get('hagenie_zone') == deviceId):
                prop,action = guessPropertyAndAction(entity_id, attributes, state.state)
                if prop is None:
                    continue
                properties.append(prop)
        return properties
    else:
        state = _hass.states.get(deviceId)
        if state is not None or state.state != 'unavailable':
            return {'name':'powerstate', 'value':state.state}
    return errorResult('IOT_DEVICE_OFFLINE')

def getControlService(action):
    i = 0
    service = ''
    for c in action:
        service += (('_' if i else '') + c.lower()) if c.isupper() else c
        i += 1
    return service

def hsv2rgb(hsvColorDic):

    h = float(hsvColorDic['hue'])
    s = float(hsvColorDic['saturation'])
    v = float(hsvColorDic['brightness'])
    rgb = color_util.color_hsv_to_RGB(h, s, v)

    return rgb

def timestamp2Delay(timestamp):
    delay = abs(int(time.time()) - timestamp)
    _LOGGER.info(delay)
    return delay

DEVICE_TYPES = [
    'TV_SET',#: '电视',
    'LIGHT',#: '灯',
    'AIR_CONDITION',#: '空调',
    'AIR_PURIFIER',#: '空气净化器',
    'AIR_MONITOR',#: '空气监测器类设备',
    'SOCKET',#: '插座',
    'SWITCH',#: '开关',
    'HEATER',#: '电暖器类设备',
    'CLOTHES_RACK',# '晾衣架',
    'GAS_STOVE',# '燃气灶类设备',
    'SWEEPING_ROBOT',#: '扫地机器人',
    'CURTAIN',#: '窗帘',
    'HUMIDIFIER',#: '加湿器',
    'FAN',#: '风扇',
    'KETTLE',#: '电热水壶',
    'RICE_COOKER',#: '电饭煲',
    'WATER_HEATER',#: '热水器',
    'OVEN',#: '烤箱',
    'WATER_PURIFIER',#: '净水器',
    'FRIDGE',#: '冰箱',
    'SET_TOP_BOX',#: '机顶盒',
    'WASHING_MACHINE',#: '洗衣机',
    'WINDOW_OPENER',#: '窗',
    'RANGE_HOOD',#: '抽油烟机',
]

INCLUDE_DOMAINS = {
    'climate': 'AIR_CONDITION',
    'fan': 'FAN',
    'light': 'LIGHT',
    'media_player': 'TV_SET',
    'switch': 'SWITCH',
    'vacuum': 'SWEEPING_ROBOT',
    'sensor': 'AIR_MONITOR',
    'cover': 'CURTAIN'

    }

EXCLUDE_DOMAINS = [
    'automation',
    'binary_sensor',
    'device_tracker',
    'group',
    'zone',
    'sun',
    ]

ALL_ACTIONS = [
    'turnOn',  # 打开
    'timingTurnOn',  # 定时打开
    'turnOff',  # 关闭
    'timingTurnOff',  # 定时关闭
    'pause',  # 暂停
    'continue',  # 继续
    'setBrightnessPercentage',  # 设置灯光亮度
    'incrementBrightnessPercentage',  # 调亮灯光
    'decrementBrightnessPercentage',  # 调暗灯光
    'incrementTemperature',  # 升高温度
    'decrementTemperature',  # 降低温度
    'setTemperature',  # 设置温度
    'incrementVolume',  # 调高音量
    'decrementVolume',  # 调低音量
    'setVolume',  # 设置音量
    'setVolumeMute',  # 设置设备静音状态
    'incrementFanSpeed',  # 增加风速
    'decrementFanSpeed',  # 减小风速
    'setFanSpeed',  # 设置风速
    'setMode',  # 设置模式
    'unSetMode',  # 取消设置的模式
    'timingSetMode',  # 定时设置模式
    'timingUnsetMode',  # 定时取消设置的模式
    'setColor',  # 设置颜色
    'getAirQualityIndex',  # 查询空气质量
    'getAirPM25',  # 查询PM2.5
    'getTemperatureReading',  # 查询温度
    'getTargetTemperature',  # 查询目标温度
    'getHumidity',  # 查询湿度
    'getTimeLeft',  # 查询剩余时间
    'getRunningTime',  # 查询运行时间
    'getRunningStatus',  # 查询运行状态
    'getWaterQuality',  # 查询水质
    'setHumidity',  # 设置湿度模式
    'setLockState',  # 上锁解锁
    'getLockState',  # 查询锁状态
    'incrementPower',  # 增大功率
    'decrementPower',  # 减小功率
    'returnTVChannel',  # 返回上个频道
    'decrementTVChannel',  # 上一个频道
    'incrementTVChannel',  # 下一个频道
    'setTVChannel',  # 设置频道
    'decrementHeight',  # 降低高度
    'incrementHeight',  # 升高高度
    'chargeTurnOn',  # 开始充电
    'chargeTurnOff',  # 停止充电
    'submitPrint', #打印
    'getTurnOnState', #查询设备打开状态
    'setSuction',  # 设置吸力
    'setDirection',  # 设置移动方向
    'getElectricityCapacity',  # 查询电量
    'getOilCapacity',  # 查询油量
]


TRANSLATIONS = {
    'cover': {
        'TurnOnRequest':  'open_cover',
        'TurnOffRequest': 'close_cover',
        'TimingTurnOnRequest': 'open_cover',
        'TimingTurnOffRequest': 'close_cover',
    },
    'vacuum': {
        'TurnOnRequest':  'start',
        'TurnOffRequest': 'return_to_base',
        'TimingTurnOnRequest': 'start',
        'TimingTurnOffRequest': 'return_to_base',
        'SetSuctionRequest': lambda state, payload: ('set_fan_speed', {'fan_speed': 90 if payload['suction']['value'] == 'STRONG' else 60}),
    },
    'switch': {
        'TurnOnRequest': 'turn_on',
        'TurnOffRequest': 'turn_off',
        'TimingTurnOnRequest': 'turn_on',
        'TimingTurnOffRequest': 'turn_off'
    },
    'light': {
        'TurnOnRequest':  'turn_on',
        'TurnOffRequest': 'turn_off',
        'TimingTurnOnRequest': 'turn_on',
        'TimingTurnOffRequest': 'turn_off',
        'SetBrightnessPercentageRequest': lambda state, payload: ('turn_on', {'brightness_pct': payload['brightness']['value']}),
        'IncrementBrightnessPercentageRequest': lambda state, payload: ('turn_on', {'brightness_pct': min(state.attributes['brightness'] / 255 * 100 + payload['deltaPercentage'][
            'value'], 100)}),
        'DecrementBrightnessPercentageRequest': lambda state, payload: ('turn_on', {'brightness_pct': max(state.attributes['brightness'] / 255 * 100 - payload['deltaPercentage']['value'], 0)}),
        'SetColorRequest': lambda state, payload: ('turn_on', {"hs_color": [float(payload['color']['hue']), float(payload['color']['saturation']) * 100]})
    },

}

def guessDeviceType(entity_id, attributes):
    deviceTypes = []
    if 'dueros_deviceType' in attributes:
        deviceTypes.append(attributes['dueros_deviceType'])

    # Exclude with domain
    domain = entity_id[:entity_id.find('.')]
    if domain in EXCLUDE_DOMAINS:
        return None

    # Guess from entity_id
    for deviceType in DEVICE_TYPES:
        if deviceType in entity_id:
            deviceTypes.append(deviceType)

    # Map from domain
    if domain in INCLUDE_DOMAINS:
        deviceTypes.append(INCLUDE_DOMAINS[domain])

    return deviceTypes


def groupsAttributes(states):
    groups_attributes = []
    for state in states:
        group_entity_id = state.entity_id
        if group_entity_id.startswith('group.') and not group_entity_id.startswith('group.all_') and group_entity_id != 'group.default_view':
            group_attributes = state.attributes
            if 'entity_id' in group_attributes:
                groups_attributes.append(group_attributes)
    return groups_attributes


def guessAction(entity_id, attributes):
    # Support On/Off/Query only at this time
    if 'dueros_actions' in attributes:
        actions = attributes['dueros_actions']
    elif entity_id.startswith('switch.'):
        actions = ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff"]
    elif entity_id.startswith('light.'):
        actions = ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff", "setBrightnessPercentage", "incrementBrightnessPercentage", "decrementBrightnessPercentage", "setColor"]
    elif entity_id.startswith('cover.'):
        actions = ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff", "pause"]
    elif entity_id.startswith('vacuum.'):
        actions = ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff", "setSuction"]
    elif entity_id.startswith('sensor.'):
        actions = ["getTemperatureReading", "getHumidity"]
    else:
        actions = ["turnOn", "timingTurnOn", "turnOff", "timingTurnOff"]

    # elif entity_id.startswith('sensor.'):
    #     unit = attributes['unit_of_measurement'] if 'unit_of_measurement' in attributes else ''
    #     if unit == u'°C' or unit == u'℃':
    #         name = 'Temperature'
    #     elif unit == 'lx' or unit == 'lm':
    #         name = 'Brightness'
    #     elif ('hcho' in entity_id):
    #         name = 'Fog'
    #     elif ('humidity' in entity_id):
    #         name = 'Humidity'
    #     elif ('pm25' in entity_id):
    #         name = 'PM2.5'
    #     elif ('co2' in entity_id):
    #         name = 'WindSpeed'
    #     else:
    #         return (None, None)
    # else:
    #     name = 'PowerState'
    #     if state != 'off':
    #         state = 'on'
    return actions
