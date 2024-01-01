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

NUM_NODES = len(NODE_NAMES)
# NUM_NODES = 8

NODE_NAME2ADDR = {k:randbytes(8) for k in NODE_NAMES}
NODE_ADDR2NAME = {v:k for k,v in NODE_NAME2ADDR.items()}

# sim node constants
DEFAULT_SPEED = 5
DEFAULT_RANGE = 200
SIM_X_MARGIN = 30
SIM_Y_MARGIN = 30
NODE_SPRITE_DIM = (20, 20)

# surfaces
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 800
SIM_HEIGHT = 600
GUI_HEIGHT = 200

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
NAME_DROPDOWN_DIM = (100, 30)
SEND_BUTTON_DIM = (100, 30)

# element positions
SEND_DROPDOWN_POS = (0, 600)
RECV_DROPDOWN_POS = (0, 630)
SEND_BUTTON_POS = (0, 660)



