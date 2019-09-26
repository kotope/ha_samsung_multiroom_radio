# HA: Samsung Multiroom Radio
Integrates Samsung Multiroom mediaplayer as a radio on Home Assistant
Works at least with Samsung WAM750

Based on https://github.com/macbury/ha_samsung_multi_room

Implemented "for my needs", feel free to contribute or do anything you like..

## Configuration example:
media_player:
  - platform: samsung_multi_room
    name: "WAM750" # optional
    host: 192.168.1.233 # ip of your soundbar
    max_volume: 20


