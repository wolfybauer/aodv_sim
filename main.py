from random import randbytes, randint, choice
import logging as log

from node import Node as AODVNode
from packet import AODVType
import sim_config as cfg

import pygame as pg
import pygame_gui as gui
from pygame_gui.elements import UIButton, UILabel, UIPanel, UIDropDownMenu, UITextBox, UIHorizontalSlider, UIStatusBar

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
    def __init__(self, parent, addr, nickname, position):
        super().__init__(parent.nodes)
        self.signals = parent.signals
        self.settings = parent.settings
        self.addr = addr
        self.nickname = nickname
        self.aodv = AODVNode(node_addr=self.addr, nickname=nickname)
        self.image = pg.Surface(cfg.NODE_SPRITE_DIM)
        self.image.fill(pg.Color(cfg.NODE_COLOR))
        self.rect = self.image.get_rect(center=position)
        self.addr_surf = font.render(self.aodv.whoami(), True, pg.Color(cfg.ADDR_COLOR))
    
    def emit_signal(self, payload=b'', color='red'):
        self.signals.add(Transmission(parent=self, payload=payload, color=color))
    
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
            elif raw[16] == AODVType.DATA: # data
                c = cfg.DATA_COLOR
            else:
                return cfg.UNKNOWN_COLOR
            self.emit_signal(raw, c)
    
    def draw_address(self, screen):
        addr_pos = self.rect.x, self.rect.y - 25
        screen.blit(self.addr_surf, addr_pos)
        
# signal class
class Transmission(pg.sprite.Sprite):
    def __init__(self, parent, payload:bytes, color:str='red'):
        super().__init__(parent.signals)
        self.src_addr = parent.addr
        self.payload = payload
        self.position = parent.rect.center
        self.speed = parent.settings.speed
        self.range = parent.settings.range  # Adjust as needed
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
    def __getitem__(self, key):
        return self.__dict__.get(key, None)
    def __init__(self):
        self.direction = PING_FWD
        self.default()
    def default(self):
        self.paused = False
        self.num_nodes = len(cfg.NODE_NAMES)
        self.sender = cfg.NODE_NAMES[0]
        self.recver = cfg.NODE_NAMES[1]
        self.range = cfg.DEFAULT_RANGE
        self.speed = cfg.DEFAULT_SPEED
        self.view_node = self.sender

class Slider(UIHorizontalSlider):
    def __init__(self, parent, label, value_range, start_value, x, y):
        r = pg.Rect((x*cfg.BUTTON_W,y*cfg.BUTTON_H,cfg.SLIDER_W,cfg.SLIDER_H))
        # super().__init__(relative_rect=pg.Rect((x*cfg.BUTTON_W,y*cfg.BUTTON_H,cfg.SLIDER_W,cfg.SLIDER_H)),
        super().__init__(relative_rect=r,
                        value_range=value_range, start_value=start_value, manager=parent.manager, container=parent)
        self.inner =  UILabel(relative_rect=r,
                                text=str(start_value),
                                manager=parent.manager,
                                container=parent)
        
        self.outer = UILabel(relative_rect=pg.Rect((r.topright[0]-r.w*0.25,r[1]), (r.w, r.h)),
                                text=str(label),
                                manager=parent.manager,
                                container=parent,)
    def set_text(self, text):
        self.inner.set_text(text)

class Button(UIButton):
    def __init__(self, parent, text, x, y):
        super().__init__(relative_rect=pg.Rect((x*cfg.BUTTON_W,y*cfg.BUTTON_H,cfg.BUTTON_W,cfg.BUTTON_H)),
                        text=text,
                        manager=parent.manager,
                        container=parent)
class Dropdown(UIDropDownMenu):
    def __init__(self, parent, options_list, start_option, x, y):
        super().__init__(relative_rect=pg.Rect((x*cfg.BUTTON_W,y*cfg.BUTTON_H,cfg.BUTTON_W,cfg.BUTTON_H)),
                         options_list=options_list,
                         starting_option=str(start_option),
                         manager=parent.manager,
                         container=parent)

class StatusBar(UIStatusBar):
    def __init__(self, parent, label, x, y, percent_method=None):
        r = pg.Rect((x*cfg.BUTTON_W,y*cfg.BUTTON_H,cfg.SLIDER_W,cfg.SLIDER_H))
        super().__init__(relative_rect=r,
                         percent_method=percent_method,
                         manager=parent.manager,
                         container=parent)
        self.inner =  UILabel(relative_rect=r,
                                text='',
                                manager=parent.manager,
                                container=parent)
        self.outer = UILabel(relative_rect=pg.Rect((r.topright[0]-r.w*0.25,r[1]), (r.w, r.h)),
                                text=str(label),
                                manager=parent.manager,
                                container=parent,)
    def set_text(self, text):
        self.inner.set_text(text)

class NodeViewer(UIPanel):
    def __init__(self, parent):
        super().__init__(pg.Rect(cfg.VIEW_DIM), manager=parent.manager)

        self.parent = parent
        self.manager = parent.manager
        self.settings = parent.settings
        self.nodes = parent.nodes
        self.signals = parent.signals
        self.sender_box = UITextBox(html_text='',
                             relative_rect=pg.Rect(0,0,cfg.VIEW_WIDTH,cfg.VIEW_HEIGHT),
                             manager=self.manager,
                             container=self,
                             plain_text_display_only=True)
        self.recver_box = UITextBox(html_text='',
                             relative_rect=pg.Rect(0,cfg.VIEW_HEIGHT//2,cfg.VIEW_WIDTH,cfg.VIEW_HEIGHT//2),
                             manager=self.manager,
                             container=self,
                             plain_text_display_only=True)
        
    def format(self, aodv:AODVNode):
        routes = {}
        out = f'NODE:{aodv.nickname}\nSEQ:{aodv.seq_num},RREQID:{aodv.rreq_id},'

    def print_active(self):
        for n in self.nodes:
            # if n.nickname == self.settings.view_node:
            if n.nickname == self.settings.sender:
                raw = n.aodv.__repr__()
                for nn in self.nodes:
                    raw = raw.replace(str(nn.addr), nn.nickname)
                self.sender_box.set_text(raw)
            if n.nickname == self.settings.recver:
                raw = n.aodv.__repr__()
                for nn in self.nodes:
                    raw = raw.replace(str(nn.addr), nn.nickname)
                self.recver_box.set_text(raw)
    
    def update(self, time_delta: float):
        self.print_active()
        return super().update(time_delta)
    

class Controller(UIPanel):
    def __init__(self, parent):
        super().__init__(pg.Rect(cfg.GUI_DIM), manager=parent.manager)

        self.parent = parent
        self.manager = parent.manager
        self.settings = parent.settings
        self.nodes = parent.nodes
        self.signals = parent.signals

        self.remake()
        self.refresh()
        
    
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
            if event.ui_element == self.default_button:
                self.settings.default()
                self.parent.reset_nodes()
                self.remake()
                self.refresh()
                handled &= True
            # default button clicked
            if event.ui_element == self.reset_button:
                self.parent.reset_nodes()
                self.remake()
                self.refresh()
                handled &= True
            # direction button clicked
            if event.ui_element == self.dir_button:
                self.parent.reverse_direction()
                handled &= True
            # random sender button
            if event.ui_element == self.random_l_button:
                self.parent.randomize('left')
                handled &= True
            # random sender button
            if event.ui_element == self.random_m_button:
                self.parent.randomize('left')
                self.parent.randomize('right')
                handled &= True
            # random recver button
            if event.ui_element == self.random_r_button:
                self.parent.randomize('right')
                handled &= True
        elif event.type == gui.UI_HORIZONTAL_SLIDER_MOVED:
            #TODO
            pass

        return handled

    def update(self, time_delta):
        super().update(time_delta)
        self.refresh()
    
    def remake(self):
        # self.manager.clear_and_reset()
        # button to send ping
        try:
            self.ping_button.kill()
            self.reset_button.kill()
            self.default_button.kill()
            self.dir_button.kill()
            self.random_l_button.kill()
            self.random_m_button.kill()
            self.random_r_button.kill()
            self.send_list.kill()
            self.recv_list.kill()
            self.num_nodes_slider.kill()
            self.range_slider.kill()
            self.signals_status.kill()
        except Exception as e:
            # print(e)
            pass

        self.random_l_button = Button(self, 'random', 0, 0)
        self.random_m_button = Button(self, 'both', 1, 0)
        self.random_r_button = Button(self, 'random', 2, 0)

        self.send_list = Dropdown(self, cfg.NODE_NAMES[:self.settings.num_nodes], self.settings.sender, 0, 1)
        self.dir_button = Button(self, PING_FWD, 1, 1)
        self.recv_list = Dropdown(self, cfg.NODE_NAMES[:self.settings.num_nodes], self.settings.recver, 2, 1)

        self.reset_button = Button(self, 'reset', 3, 0)
        self.default_button = Button(self, 'default', 3, 1)
        self.ping_button = Button(self, 'ping', 4, 0)

        self.range_slider = Slider(self, 'range', (cfg.MIN_RANGE,cfg.MAX_RANGE), self.settings.range, 6, 0)
        self.num_nodes_slider = Slider(self, 'nodes', (3,len(cfg.NODE_NAMES)), self.settings.num_nodes, 6, 1)

        self.signals_status = StatusBar(self, 'signals', 6, 2, self.signals.__len__)
    
    def refresh(self):
        self.settings.sender = self.send_list.selected_option
        self.settings.recver = self.recv_list.selected_option
        self.settings.num_nodes = self.num_nodes_slider.current_value
        self.settings.range = self.range_slider.current_value
        self.num_nodes_slider.set_text(str(self.settings.num_nodes))
        self.range_slider.set_text(str(self.settings.range))
        self.signals_status.set_text(str(len(self.signals)))

class Simulation:
    def __init__(self):
        pg.init()
        pg.display.set_caption('aodv sim')

        self.running = True
        self.settings = Settings()

        self.screen = pg.display.set_mode((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))
        self.manager = gui.UIManager((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))
        
        self.sim_surf = pg.Surface((cfg.SCREEN_WIDTH,cfg.SIM_HEIGHT))
        self.sim_surf.fill(cfg.SIM_COLOR)

        self.clock = pg.time.Clock()
        self.nodes = pg.sprite.Group()
        self.signals = pg.sprite.Group()

        self.ctl = Controller(self)
        self.view = NodeViewer(self)

        self.reset_nodes()
    
    def name2addr(self, nickname):
        for n in self.nodes:
            if n.nickname == nickname:
                return n.addr
        return None
    
    def randomize(self, side='left'):
        if side == 'left':
            old = self.settings.sender
            self.settings.sender = choice(cfg.NODE_NAMES[:self.settings.num_nodes])
            while (self.settings.sender == self.settings.recver or
                   self.settings.sender == old):
                self.settings.sender = choice(cfg.NODE_NAMES[:self.settings.num_nodes])
        else:
            old = self.settings.recver
            self.settings.recver = choice(cfg.NODE_NAMES[:self.settings.num_nodes])
            while (self.settings.recver == self.settings.sender or
                   self.settings.recver == old):
                self.settings.recver = choice(cfg.NODE_NAMES[:self.settings.num_nodes])
        self.ctl.remake()
        self.ctl.refresh()
    
    def reverse_direction(self):
        if self.settings.direction == PING_FWD:
            self.settings.direction = PING_REV
        else:
            self.settings.direction = PING_FWD
        self.ctl.dir_button.set_text(self.settings.direction)

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
        for n in cfg.NODE_NAMES[:self.settings.num_nodes]:
            x = randint(cfg.SIM_X_MARGIN, cfg.SIM_WIDTH - cfg.SIM_X_MARGIN)
            y = randint(cfg.SIM_Y_MARGIN, cfg.SIM_HEIGHT - cfg.SIM_Y_MARGIN)
            node = SimNode(self, randbytes(8), n, (x,y))
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
                    # default settings
                    if event.key == pg.K_d:
                        self.settings.default()
                        self.reset_nodes()
                        self.ctl.remake()
                        self.ctl.refresh()
                    # reset
                    if event.key == pg.K_r:
                        self.reset_nodes()
                        self.ctl.remake()
                        self.ctl.refresh()
                    # ping
                    if event.key == pg.K_p:
                        self.ctl.send_ping()
                    # direction
                    if event.key == pg.K_s:
                        self.reverse_direction()
                    # randomize sender
                    if event.key == pg.K_q:
                        self.randomize('left')
                    # randomize both
                    if event.key == pg.K_w:
                        self.ctl.random_m_button.held = True
                        self.randomize('left')
                        self.randomize('right')
                    # randomize recver
                    if event.key == pg.K_e:
                        self.randomize('right')

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
                for s in self.signals:
                    s.draw(self.sim_surf)
                for n in self.nodes:
                    n.draw_address(self.screen)
                self.manager.draw_ui(self.screen)
                
                pg.display.update()

if __name__ == '__main__':
    sim = Simulation()
    sim.run()