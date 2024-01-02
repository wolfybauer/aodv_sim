from random import randbytes, randint
import logging as log

from node import Node as AODVNode
from packet import AODVType
import sim_config as cfg

import pygame as pg
import pygame_gui as gui
from pygame_gui.elements import UIButton, UILabel, UIPanel, UIDropDownMenu, UITextBox

PING_FWD = '>>>>>>>>'
PING_REV = '<<<<<<<<'

# set up logger
log_fmt = '%(asctime)s:%(levelname)s:%(message)s'
log_datefmt = "%H:%M:%S"
log.basicConfig(level=20, format=log_fmt, datefmt=log_datefmt)

# pg surface stuff
pg.init()
font = pg.font.Font(None, 24)
# bg_sim = pg.Surface((cfg.SIM_WIDTH,cfg.SIM_HEIGHT))
# bg_sim.fill(pg.Color(cfg.SIM_COLOR))

# node class
class SimNode(pg.sprite.Sprite):
    def __init__(self, nodes_group, signals_group, addr, nickname, position):
        super().__init__(nodes_group)
        self.signals = signals_group
        self.addr = addr
        self.nickname = nickname
        self.aodv = AODVNode(node_addr=self.addr, nickname=nickname)
        self.image = pg.Surface(cfg.NODE_SPRITE_DIM)
        self.image.fill(pg.Color(cfg.NODE_COLOR))
        self.rect = self.image.get_rect(center=position)
        self.addr_surf = font.render(self.aodv.whoami(), True, pg.Color(cfg.ADDR_COLOR))
    
    def emit_signal(self, payload=b'', color='red'):
        self.signals.add(Transmission(self.signals, src_addr=self.addr, payload=payload, position=self.rect.center, color=color))
    
    def update(self):
        raw = self.aodv.update()

        # get signal type for color
        if raw:
            if len(raw) < 24:
                c = cfg.UNKNOWN_COLOR
            elif raw[16] == AODVType.RREQ: # rreq
                c = cfg.RREQ_COLOR
            elif raw[16] == AODVType.RREP: # rrep
                c = cfg.RREP_COLOR
            elif raw[16] == AODVType.RERR: # rerr
                c = cfg.RERR_COLOR
            elif raw[16] == AODVType.HELLO: # hello
                c = cfg.HELLO_COLOR
            elif raw[16] == AODVType.DATA: # hello
                c = cfg.DATA_COLOR
            else:
                return cfg.UNKNOWN_COLOR
            self.emit_signal(raw, c)
    
    def draw_address(self, screen):
        addr_pos = self.rect.x, self.rect.y - 25
        screen.blit(self.addr_surf, addr_pos)
        
# signal class
class Transmission(pg.sprite.Sprite):
    def __init__(self, signals_group, src_addr:bytes, payload:bytes, position:tuple, color:str='red', speed:int=cfg.DEFAULT_SPEED, range:int=cfg.DEFAULT_RANGE):
        super().__init__(signals_group)
        self.src_addr = src_addr
        self.payload = payload
        self.position = position
        self.speed = speed
        self.range = range  # Adjust as needed
        self.radius = 1
        self.collided = []
        try:
            self.color = pg.Color(color)
        except Exception as e:
            print(e)
            log.warning('ERROR setting default color: red')
            self.color = pg.Color('red')

    def update(self):
        self.radius += self.speed
        if self.radius > self.range:
            self.kill()  # Remove the sprite when it reaches max radius

    def draw(self, surface):
        pg.draw.circle(surface, self.color, self.position, self.radius, 1)

class Settings:
    def __init__(self):
        self.paused = False
        self.num_nodes = len(cfg.NODE_NAMES)
        self.sender = cfg.NODE_NAMES[0]
        self.recver = cfg.NODE_NAMES[1]
        self.direction = PING_FWD

class NodeViewer(UIPanel):
    def __init__(self, parent, manager, settings, nodes_group, signals_group):
        super().__init__(pg.Rect(cfg.VIEW_DIM), manager=manager)
        
        self.parent = parent
        self.manager = manager
        self.settings = settings
        self.nodes = nodes_group
        self.signals = signals_group

        self.active_node = None
        self.box = UITextBox(html_text='hello',
                             relative_rect=pg.Rect(0,0,cfg.VIEW_WIDTH,cfg.VIEW_HEIGHT),
                             manager=self.manager,
                             container=self,
                             plain_text_display_only=True)
        

class Controller(UIPanel):
    def __init__(self, parent, manager, settings, nodes_group, signals_group):
        super().__init__(pg.Rect(cfg.GUI_DIM), manager=manager)

        self.parent = parent
        self.manager = manager
        self.settings = settings
        self.nodes = nodes_group
        self.signals = signals_group

        # button to send ping
        self.ping_button = UIButton(relative_rect=pg.Rect((0,0),(cfg.BUTTON_W,cfg.BUTTON_H)),
                                    text='ping',
                                    manager=self.manager,
                                    container=self)
        # button to send ping
        self.reset_button = UIButton(relative_rect=pg.Rect((cfg.BUTTON_W,0),(cfg.BUTTON_W,cfg.BUTTON_H)),
                                    text='reset',
                                    manager=self.manager,
                                    container=self)
        # button to switch send direction
        self.dir_button = UIButton(relative_rect=pg.Rect((0,cfg.BUTTON_H*2),(cfg.BUTTON_W,cfg.BUTTON_H)),
                                                text='',
                                                manager=self.manager,
                                                container=self)
        # direction button label
        self.dir_label = UILabel(relative_rect=self.dir_button.relative_rect,
                                 text=self.settings.direction,
                                 manager=self.manager,
                                 container=self)
        # left node list
        self.send_list = UIDropDownMenu(relative_rect=pg.Rect(0,cfg.BUTTON_H,cfg.BUTTON_W,cfg.BUTTON_H), 
                                         options_list=cfg.NODE_NAMES,
                                         manager=self.manager,
                                         container=self,
                                         starting_option=cfg.NODE_NAMES[0])
        #right node list
        self.recv_list = UIDropDownMenu(relative_rect=pg.Rect(0,cfg.BUTTON_H*3,cfg.BUTTON_W,cfg.BUTTON_H),
                                         options_list=cfg.NODE_NAMES,
                                         manager=self.manager,
                                         container=self,
                                         starting_option=cfg.NODE_NAMES[1])
    
    def send_ping(self):
        if self.settings.direction == PING_FWD:
            s = self.settings.sender
            r = self.settings.recver
        else:
            r = self.settings.sender
            s = self.settings.recver
        for node in self.nodes:
            if node.nickname == s:
                node.aodv.send(self.parent.name2addr(r), 'ping')
        log.info(f'{self.settings.sender}>>>{self.settings.recver}')
        return True
    
    def process_event(self, event):
        handled = super().process_event(event)

        if event.type == gui.UI_BUTTON_PRESSED:

            # ping button clicked
            if event.ui_element == self.ping_button:
                handled &= self.send_ping()
            # reset button clicked
            if event.ui_element == self.reset_button:
                self.parent.reset_nodes()
                handled &= True
            # direction button clicked
            if event.ui_element == self.dir_button:
                if self.settings.direction == PING_FWD:
                    self.settings.direction = PING_REV
                else:
                    self.settings.direction = PING_FWD
                self.dir_label.set_text(self.settings.direction)
                handled &= True

        return handled

    def update(self, time_delta):
        super().update(time_delta)
        self.settings.sender = self.send_list.selected_option
        self.settings.recver = self.recv_list.selected_option



class Simulation:
    def __init__(self):
        pg.init()
        pg.display.set_caption('controller test')

        self.running = True
        self.settings = Settings()

        self.screen = pg.display.set_mode((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))
        self.manager = gui.UIManager((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))
        
        self.sim_surf = pg.Surface((cfg.SCREEN_WIDTH,cfg.SIM_HEIGHT))
        self.sim_surf.fill(cfg.SIM_COLOR)

        self.clock = pg.time.Clock()
        self.nodes = pg.sprite.Group()
        self.signals = pg.sprite.Group()

        self.ctl = Controller(self, self.manager, self.settings, self.nodes, self.signals)
        self.view = NodeViewer(self, self.manager, self.settings, self.nodes, self.signals)

        self.reset_nodes()
    
    def name2addr(self, nickname):
        for n in self.nodes:
            if n.nickname == nickname:
                return n.addr
        return None

    def detect_collisions(self):
        for signal in self.signals:
            for node in self.nodes:
                # check collisions
                if not signal.src_addr == node.addr:
                    # get distance to node
                    node_center = pg.Vector2(node.rect.center)
                    signal_center = pg.Vector2(signal.position)
                    distance = node_center.distance_to(signal_center)

                    # colliding = distance < signal.radius
                    if distance < signal.radius:
                        if not node.addr in signal.collided:
                            signal.collided.append(node.addr)
                            node.aodv.on_recv(signal.payload)
    
    # generate random nodes
    def reset_nodes(self):
        # clear old stuff
        self.nodes.empty()
        self.signals.empty()
        self.sim_surf.fill(pg.Color(cfg.SIM_COLOR))
        # create some nodes
        for n in cfg.NODE_NAMES:
            x = randint(cfg.SIM_X_MARGIN, cfg.SIM_WIDTH - cfg.SIM_X_MARGIN)
            y = randint(cfg.SIM_Y_MARGIN, cfg.SIM_HEIGHT - cfg.SIM_Y_MARGIN)
            node = SimNode(self.nodes, self.signals, randbytes(8), n, (x,y))
            self.nodes.add(node)

    def run(self):
        while self.running:
            # lock fps
            dt = self.clock.tick(cfg.FPS) / 1000.0

            # event loops
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.running = False

                # keyboard shortcuts
                if event.type == pg.KEYDOWN:
                    # esc
                    if event.key == pg.K_ESCAPE:
                        self.running = False
                    # reset
                    elif event.key == pg.K_r:
                        self.reset_nodes()

                self.manager.process_events(event)

            if not self.settings.paused:
                # logical stuff
                self.manager.update(dt)
                self.signals.update()
                self.nodes.update()
                self.detect_collisions()

                # graphical stuff
                self.screen.blit(self.sim_surf, (0, 0))
                self.sim_surf.fill(cfg.SIM_COLOR)
                self.nodes.draw(self.sim_surf)
                self.manager.draw_ui(self.screen)
                for s in self.signals:
                    s.draw(self.sim_surf)
                for n in self.nodes:
                    n.draw_address(self.screen)
                pg.display.update()

if __name__ == '__main__':
    sim = Simulation()
    sim.run()