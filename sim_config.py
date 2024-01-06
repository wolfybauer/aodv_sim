from random import randbytes

FPS = 60

# node names
NODE_NAMES = ['john',
              'morgan',
              'frank',
              'tim',
              'dianne',
              'nicholas',
              'inez',
              'kwame',
              'abdullah',
              'narin',
              'tasnim',
              'felix',
              'joaquin',
              'fatima',
              'mahilet',
              'antonio',
              'wolfgang',
              'sigmund',
              'ralph',
              'tiffany',
              'alicia',
              'naomi',
              'penny',
              'oliver',
              'rakim',
              'huey',
              'malik']

# sim node constants
DEFAULT_SPEED = 5
DEFAULT_RANGE = 180
MAX_RANGE = 400
MIN_RANGE = 50
MAX_SPEED = 20
MIN_SPEED = 1
SIM_X_MARGIN = 30
SIM_Y_MARGIN = 30
NODE_SPRITE_DIM = (20, 20)

# surfaces
SIM_WIDTH = 800
SIM_HEIGHT = 600
GUI_HEIGHT = 210
VIEW_WIDTH = 400

GUI_WIDTH = SIM_WIDTH
BUTTON_W = SIM_WIDTH//8
BUTTON_H = GUI_HEIGHT//7

GUI_HEIGHT = BUTTON_H*7
SCREEN_HEIGHT = SIM_HEIGHT+GUI_HEIGHT
SCREEN_WIDTH = SIM_WIDTH+VIEW_WIDTH*2
VIEW_HEIGHT = SCREEN_HEIGHT

# colors
SIM_COLOR = 'black'
GUI_COLOR = 'pink'
NODE_COLOR =  'white'
RREQ_COLOR = 'purple'
RREP_COLOR = 'blue'
RERR_COLOR = 'red'
HELLO_COLOR = 'yellow'
DATA_COLOR = 'green'
UNKNOWN_COLOR = 'white'
OFFLINE_COLOR = 'red'


# element dimensions
SLIDER_W = int(BUTTON_W * 1.25)
SLIDER_H = BUTTON_H

INFOBOX_W = VIEW_WIDTH
INFOBOX_H = BUTTON_H * 2
DATABOX_W = VIEW_WIDTH
DATABOX_H = SCREEN_HEIGHT - INFOBOX_H - BUTTON_H

# element positions
SEND_DROPDOWN_POS = (0, 600)
RECV_DROPDOWN_POS = (0, 630)
SEND_BUTTON_POS = (0, 660)

SIM_DIM = (0, 0, SIM_WIDTH, SIM_HEIGHT)
GUI_DIM = (0, SIM_HEIGHT, GUI_WIDTH, GUI_HEIGHT)
VIEW_DIM = [(SIM_WIDTH, 0, VIEW_WIDTH, VIEW_HEIGHT),
            (SIM_WIDTH+VIEW_WIDTH, 0, VIEW_WIDTH, VIEW_HEIGHT)]
