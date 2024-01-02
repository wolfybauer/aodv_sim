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
              'ralph']

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
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
SIM_WIDTH = 800
SIM_HEIGHT = 600

GUI_WIDTH = SIM_WIDTH
GUI_HEIGHT = SCREEN_HEIGHT - SIM_HEIGHT
VIEW_HEIGHT = SCREEN_HEIGHT
VIEW_WIDTH = SCREEN_WIDTH - SIM_WIDTH

# colors
SIM_COLOR = 'black'
GUI_COLOR = 'pink'
NODE_COLOR =  'white'
ADDR_COLOR = 'white'
RREQ_COLOR = 'purple'
RREP_COLOR = 'blue'
RERR_COLOR = 'red'
HELLO_COLOR = 'yellow'
DATA_COLOR = 'green'
UNKNOWN_COLOR = 'white'

# element dimensions
BUTTON_W = 100
BUTTON_H = 30

SLIDER_W = int(BUTTON_W * 1.5)
SLIDER_H = BUTTON_H

# element positions
SEND_DROPDOWN_POS = (0, 600)
RECV_DROPDOWN_POS = (0, 630)
SEND_BUTTON_POS = (0, 660)

SIM_DIM = (0, 0, SIM_WIDTH, SIM_HEIGHT)
GUI_DIM = (0, SIM_HEIGHT, GUI_WIDTH, GUI_HEIGHT)
VIEW_DIM = (SIM_WIDTH, 0, VIEW_WIDTH, VIEW_HEIGHT)

