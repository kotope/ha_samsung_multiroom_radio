#
# TODO: Permanent storage for received channels if multiroom speaker is offline -> cannot be fetched
# TODO: Maybe somehow handle the offline situation if network connection can not be established
#
# Code base on https://github.com/macbury/ha_samsung_multi_room/tree/master/media_player
#
# @author Toni Korhonen
#


import urllib.parse
import requests
import logging
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['xmltodict==0.12.0']
DEPENDENCIES = ['http']

import xmltodict

from homeassistant.helpers import config_validation as cv

from homeassistant.components.media_player.const import (
  MEDIA_TYPE_CHANNEL,
  SUPPORT_PLAY,
  SUPPORT_STOP,
  SUPPORT_PAUSE,
  SUPPORT_TURN_ON,
  SUPPORT_TURN_OFF,
  SUPPORT_VOLUME_MUTE,
  SUPPORT_SELECT_SOURCE,
  SUPPORT_VOLUME_SET,
)

from homeassistant.components.media_player import (
  PLATFORM_SCHEMA,
  MediaPlayerDevice
)

from homeassistant.const import (
  CONF_NAME,
  CONF_HOST,
  STATE_IDLE,
  STATE_PLAYING,
  STATE_PAUSED,
  STATE_OFF
)

BOOL_OFF = 'off'
BOOL_ON = 'on'

SUPPORT_SAMSUNG_MULTI_ROOM = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | SUPPORT_SELECT_SOURCE | SUPPORT_PLAY | SUPPORT_STOP | SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF

CONF_MAX_VOLUME = 'max_volume'
CONF_PORT = 'port'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
  vol.Required(CONF_HOST, default='127.0.0.1'): cv.string,
  vol.Optional(CONF_PORT, default='55001'): cv.string,
  vol.Optional(CONF_MAX_VOLUME, default='100'): cv.string
})


class MultiRoomApi():
  def __init__(self, ip, port):
    _LOGGER.debug("init multiroom..")
    self.ip = ip
    self.port = port
    self.endpoint = 'http://{0}:{1}'.format(ip, port)

  def _exec_cmd(self, prt, cmd, key_to_extract):
    import xmltodict
    query = urllib.parse.urlencode({ "cmd": cmd }, quote_via=urllib.parse.quote)
    url = '{0}/{1}?{2}'.format(self.endpoint, prt, query)

    req = requests.get(url, timeout=10)
    response = xmltodict.parse(req.text)
    _LOGGER.debug("response="+req.text)

    try:
      return response['UIC']['response'][key_to_extract]
    except:
       return '' # Response could not be exctracted

  def _exec_get(self, action, key_to_extract):
    return self._exec_cmd('UIC', '<name>{0}</name>'.format(action), key_to_extract)

  def _exec_set(self, prt, action, property_name, value):
    if type(value) is str:
      value_type = 'str'
    else:
      value_type = 'dec'
    cmd = '<name>{0}</name><p type="{3}" name="{1}" val="{2}"/>'.format(action, property_name, value, value_type)
    return self._exec_cmd(prt, cmd, property_name)

  def _exec_set_radio(self, prt, action, property_name, value, property2_name, value2):
    if type(value) is str:
      value_type = 'str'
    else:
      value_type = 'dec'
    if type(value2) is str:
      value2_type = 'str'
    else:
      value2_type = 'dec'
    cmd = '<name>{0}</name><p type="{3}" name="{1}" val="{2}"/><p type="{6}" name="{4}" val="{5}"/>'.format(action, property_name, value, value_type, property2_name, value2, value2_type)
    _LOGGER.debug("cmd="+cmd)
    return self._exec_cmd(prt, cmd, "playtime") # Last parameter is what we are looking for ..

  def get_main_info(self):
    return self._exec_get('GetMainInfo')

  def get_volume(self):
    return int(self._exec_get('GetVolume', 'volume'))

  def set_volume(self, volume):
    return self._exec_set('UIC', 'SetVolume', 'volume', int(volume))

  def media_play_pause(self, state):
    _LOGGER.debug("media play/pause called")
    if state == STATE_PLAYING:
      return self.media_pause()
    else:
      return self.media_play()

  def media_play(self):
    _LOGGER.debug("media play called")
    res = self._exec_set('CPM', 'SetPlaybackControl', 'playbackcontrol', 'play')
    _LOGGER.debug("result="+res)
    if not res:
      return self._exec_set_radio('CPM', 'SetPlayPreset', 'presetindex', 0, 'presettype', 1)
    else:
      return res

  def media_stop(self):
    _LOGGER.debug("media stop called")
    return self._exec_set('CPM', 'SetPlaybackControl', 'playbackcontrol', 'stop')

  def media_pause(self):
    _LOGGER.debug("media pause called")
    return self._exec_set('CPM', 'SetPlaybackControl', 'playbackcontrol', 'pause')

  def get_speaker_name(self):
    return self._exec_get('GetSpkName', 'spkname')

  def get_muted(self):
    return self._exec_get('GetMute', 'mute') == BOOL_ON

  def set_muted(self, mute):
    if mute:
      return self._exec_set('UIC', 'SetMute', 'mute', BOOL_ON)
    else:
      return self._exec_set('UIC', 'SetMute', 'mute', BOOL_OFF)

  def get_source(self):
    return self._exec_get('GetFunc', 'function')

  def get_current_radio(self):
    import xmltodict
    cmd = '<name>GetRadioInfo</name>' # Command to get the whole list
    query = urllib.parse.urlencode({ "cmd": cmd }, quote_via=urllib.parse.quote)
    url = '{0}/{1}?{2}'.format(self.endpoint, 'CPM', query)
    req = requests.get(url, timeout=10)
#    _LOGGER.debug("response="+req.text)
    response = xmltodict.parse(req.text)
    info = {}
    try:
      info = response['CPM']['response']
      if 'title' in info.keys():
        _LOGGER.debug('station='+info['title'])
      else:
        _LOGGER.debug('station could not be fetched, radio is off')
    except:
      _LOGGER.debug('failed to read the response from get_current_radio')

    return info

  def set_source(self, source, presets):
    # Source in this api is the preset name, and we need to set it up as an index
    index = 0
    _LOGGER.debug('source='+source)

    #presets = ordered dict
    #index should be found from dict['contentId']
    for x in presets:
      if x['title'] == source:
        index = x['contentid']
        break
    self._current_source = source # set the source as current source

    _LOGGER.debug('index='+index)
    return self._exec_set_radio('CPM', 'SetPlayPreset', 'presetindex', int(index), 'presettype', 1)

  def get_radio_list(self): # Get the current preset tunein stations
    import xmltodict
    cmd = '<name>GetPresetList</name><p type="dec" name="startindex" val="0"/><p type="dec" name="listcount" val="100"/>' # Command to get the whole list
    query = urllib.parse.urlencode({ "cmd": cmd }, quote_via=urllib.parse.quote)
    url = '{0}/{1}?{2}'.format(self.endpoint, 'CPM', query)
    req = requests.get(url, timeout=10)
    _LOGGER.debug("response="+req.text)
    response = xmltodict.parse(req.text)
    presetlist = []
    presets = []

    try:
      presetlist = response['CPM']['response']['presetlist']
      for k, v in presetlist.items():
        for l in v:
          presets.append(l)
    except:
      _LOGGER.debug("Could not get the preset list, use empty array and try again later")

    return presets

class MultiRoomDevice(MediaPlayerDevice):
  def __init__(self, name, max_volume, api):
    self._name = name
    self.api = api
    self._state = STATE_OFF
    self._current_source = None
    self._volume = 0
    self._muted = False
    self._max_volume = max_volume
    self.update_once()
    self.update()

  @property
  def supported_features(self):
    return SUPPORT_SAMSUNG_MULTI_ROOM

  @property
  def name(self):
    return self._name

  @property
  def state(self):
    return self._state

  @property
  def volume_level(self):
    return self._volume

  def set_volume_level(self, volume):
    self.api.set_volume(volume * self._max_volume)

  @property
  def source(self):
    return self._current_source

  @property
  def source_list(self):
    # presets is a array of dictionaries
    arr = []
    for v in self.presets:
      arr.append(v['title'])
    return arr

  def select_source(self, source):
    self.api.set_source(source, self.presets)

  def media_play_pause(self):
    self.api.media_play_pause(self._state)

  def media_play(self):
    self.api.media_play()

  def media_stop(self):
    self.api.media_stop()

  def media_pause(self):
    self.api.media_pause()

  @property
  def is_volume_muted(self):
    return self._muted

  def mute_volume(self, mute):
    self._muted = mute
    self.api.set_muted(self._muted)

  def turn_off(self):
    self.api.media_stop()

  def turn_on(self):
    self.api.media_play()

#  def media_next_track(self): #SUPPORT_NEXT_TRACK
#  def media_previous_track(self): #SUPPORT_PREVIOUS_TRACK 


  def update_once(self):
    try:
      self.presets = self.api.get_radio_list()
    except requests.exceptions.ReadTimeout as e:
      _LOGGER.error('Failed to get the preset list: :', e)

  def update(self):
    try:
      _LOGGER.info('Refreshing state...')
      if not self._name:
        self._name = self.api.get_speaker_name()
#      self._current_source = self.api.get_source()
      radioInfo = self.api.get_current_radio()
      if radioInfo:
        if 'title' in radioInfo.keys():
          self._current_source = radioInfo['title']
        else:
          self.current_source = ""
      else:
        self.current_source = ""

      self._volume = self.api.get_volume() / self._max_volume
#      self._state = STATE_IDLE # radioInfo['playstatus'] (play, stop)
      if radioInfo['playstatus'] == 'play':
        self._state = STATE_PLAYING
      else:
        self._state = STATE_IDLE

      if not self.presets: # No presets found, try again
        self.update_once()

      self._muted = self.api.get_muted()
    except requests.exceptions.ReadTimeout as e:
      self._state = STATE_OFF
      _LOGGER.error('Epic failure:', e)


def setup_platform(hass, config, add_devices, discovery_info=None):
  ip = config.get(CONF_HOST)
  port = config.get(CONF_PORT)
  name = config.get(CONF_NAME)
  max_volume = int(config.get(CONF_MAX_VOLUME))
  api = MultiRoomApi(ip, port)
  add_devices([MultiRoomDevice(name, max_volume, api)], True)
