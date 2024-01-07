import time
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
        self.addr_surf = font.render(self.aodv.whoami(), True, pg.Color(cfg.NODE_COLOR))
        self.inbox = []
        self.online = True
    
    def emit_signal(self, payload=b'', color='red'):
        self.signals.add(Transmission(parent=self, payload=payload, color=color))
    
    def update(self, events=[]):

        # if click on node
        for event in events:
            if event.type == pg.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
                self.toggle_online()

        # update aodv if node online
        if self.online:
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
            
            rx = self.aodv.pop_rx()
            if rx:
                self.inbox.append(rx)
    
    def draw_address(self, screen):
        addr_pos = self.rect.x, self.rect.y - 25
        screen.blit(self.addr_surf, addr_pos)
    
    def toggle_online(self):
        self.online = not self.online
        if self.online:
            self.image.fill(pg.Color(cfg.NODE_COLOR))
            self.addr_surf = font.render(self.aodv.whoami(), True, pg.Color(cfg.NODE_COLOR))
        else:
            self.image.fill(pg.Color(cfg.OFFLINE_COLOR))
            self.addr_surf = font.render(self.aodv.whoami(), True, pg.Color(cfg.OFFLINE_COLOR))
    
        
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
        self.color = pg.Color(color)

    def update(self):
        self.radius += self.speed
        if self.radius > self.range:
            self.kill()  # Remove the sprite when it reaches max radius

    def draw(self, surface):
        pg.draw.circle(surface, self.color, self.position, self.radius, 1)

#TODO
class Ping:
    def __init__(self, addr, timeout_s = 3):
        self.timestamp = time.time()
        self.addr = addr
        self.timeout = self.timestamp + timeout_s
        self.success = False
        self.expired = False
    def update(self):
        if not self.expired:
            if time.time() > self.timeout:
                self.expired = True
    
class Settings:
    def __getitem__(self, key):
        return self.__dict__.get(key, None)
    def __setitem__(self, key, val):
        if key in self.__dict__.keys():
            self.__setattr__(key, val)
    def __init__(self):
        self.default()
    def default(self):
        self.paused = False
        self.direction = PING_FWD
        self.num_nodes = len(cfg.NODE_NAMES)
        self.sender = cfg.NODE_NAMES[0]
        self.recver = cfg.NODE_NAMES[1]
        self.range = cfg.DEFAULT_RANGE
        self.speed = cfg.DEFAULT_SPEED

class Slider(UIHorizontalSlider):
    def __init__(self, parent, label, value_range, start_val, callback, x, y):
        self._update = lambda: self.inner.set_text(str(self.get_current_value()))
        self._process = lambda: callback(self.get_current_value())
        r = pg.Rect((x*cfg.BUTTON_W,y*cfg.BUTTON_H,cfg.SLIDER_W,cfg.SLIDER_H))
        super().__init__(relative_rect=r,
                        value_range=value_range, start_value=start_val, manager=parent.manager, container=parent)
        self.inner =  UILabel(relative_rect=r,
                                text=str(start_val),
                                manager=parent.manager,
                                container=parent)
        
        self.outer = UILabel(relative_rect=pg.Rect((r.topright[0]-r.w*0.25,r[1]), (r.w, r.h)),
                                text=str(label),
                                manager=parent.manager,
                                container=parent,)
    
    def update(self, time_delta: float):
        self._update()
        return super().update(time_delta)
    
    def process_event(self, event: pg.Event) -> bool:
        if event.type == gui.UI_HORIZONTAL_SLIDER_MOVED:
            if event.ui_element == self:
                self._process()
                self._update()
        return super().process_event(event)
        

class Button(UIButton):
    def __init__(self, parent, text, funcs, x, y):
        if not isinstance(funcs, list):
            self.func_list = [funcs]
        else:
            self.func_list = funcs
        super().__init__(relative_rect=pg.Rect((x*cfg.BUTTON_W,y*cfg.BUTTON_H,cfg.BUTTON_W,cfg.BUTTON_H)),
                        text=text,
                        manager=parent.manager,
                        container=parent)
    
    def process_event(self, event: pg.Event) -> bool:
        if event.type == gui.UI_BUTTON_PRESSED:

            if event.ui_element == self:
                for func in self.func_list:
                    func()

        return super().process_event(event)

class Dropdown(UIDropDownMenu):
    def __init__(self, parent, options_list, start_option, callback, x, y):
        self.callback = callback
        super().__init__(relative_rect=pg.Rect((x*cfg.BUTTON_W,y*cfg.BUTTON_H,cfg.BUTTON_W,cfg.BUTTON_H)),
                         options_list=options_list,
                         starting_option=str(start_option),
                         manager=parent.manager,
                         container=parent)
    
    def process_event(self, event: pg.Event) -> bool:
        if event.type == gui.UI_DROP_DOWN_MENU_CHANGED:

            if event.ui_element == self:
                self.callback(self.selected_option)

        return super().process_event(event)

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
    
    def update(self, time_delta: float):
        self.inner.set_text(str(self.percent_method()))
        return super().update(time_delta)

class NodeViewer(UIPanel):
    def __init__(self, parent, which_node, x_pos):
        super().__init__(pg.Rect(cfg.VIEW_DIM[x_pos]), manager=parent.manager)

        self.parent = parent
        self.manager = parent.manager
        self.settings = parent.settings
        self.which = which_node
        self.x_pos = x_pos

        self.mode = 'routes'
        self.active_node = lambda: self.parent.name2node[self.settings[which_node]]

        # buttons
        # self.routes_button = Button(self, 'routes', lambda: self.set_mode('routes'), 0, 0)
        # self.inbox_button = Button(self, 'inbox', lambda: self.set_mode('inbox'), 1, 0)
        self.random_button = Button(self, 'random', lambda: self.parent.randomize(self.which), 2, 0)
        self.online_button = Button(self, 'online', lambda: self.active_node().toggle_online(), 3, 0)
        
        # main view boxes
        self.info_box = UITextBox(html_text='',
                             relative_rect=pg.Rect(0,cfg.BUTTON_H,cfg.INFOBOX_W,cfg.INFOBOX_H),
                             manager=self.manager,
                             container=self,
                             plain_text_display_only=True)
        self.data_box = UITextBox(html_text='',
                             relative_rect=pg.Rect(0,cfg.BUTTON_H*3,cfg.VIEW_WIDTH,cfg.VIEW_HEIGHT),
                             manager=self.manager,
                             container=self,
                             plain_text_display_only=True)

        self.refresh()

    
    def set_mode(self, mode):
        self.mode = mode
    
    # rebuild all dropdowns
    def refresh(self):
        try:
            self.node_dropdown.kill()
            self.mode_dropdown.kill()
        except Exception as e:
            log.debug(f'SIM:{e}')
        self.node_dropdown = Dropdown(self, options_list=cfg.NODE_NAMES[:self.settings.num_nodes],
                                      start_option=self.settings[self.which],
                                      callback=lambda s: self.settings.__setattr__(self.which, s),
                                      x=0, y=0)
        self.mode_dropdown = Dropdown(self, options_list=['routes', 'neighbors', 'inbox', 'stats'],
                                      start_option=self.mode,
                                      callback=self.set_mode,
                                      x=1, y=0)
    
    def _print_info(self):
        n = self.active_node()
        out = f'NODE:{n.nickname}{f"|| {self.mode}":<6}'
        out += f'\nSEQ:{n.aodv.seq_num:04},RREQID:{n.aodv.rreq_id:04}'
        self.info_box.set_text(out)

    def _print_routes(self):
        a2n = self.parent.addr2name
        n = self.active_node()
        out = f'\n{"NAME":<9}{"NEXT":<9}{"SEQ":<8}{"HOPS":<5}{"LIFE":<5}{"VALID"}'
        for k,v in n.aodv.routing_table.items():
            out += f'\n{a2n[k]:<9}{a2n.get(v.next_hop, "???"):<9}{v.seq_num:<8}{v.hops:<5}{v.remaining():<5}{v.valid()}'
        self.data_box.set_text(out)
        
    def _print_inbox(self):
        a2n = self.parent.addr2name
        n = self.active_node()
        out = ''
        for m in n.inbox:
            out += f'\n{a2n[m.orig_addr]}[{m.orig_seq:04}]:{m.data}'
        self.data_box.set_text(out)
        
    def _print_stats(self):
        out = 'todo: stats'
        self.data_box.set_text(out)
    
    def _print_neighbors(self):
        out = 'todo: neighbors'
        self.data_box.set_text(out)
    
    def update(self, time_delta: float):
        # update button text
        if self.active_node().online:
            self.online_button.set_text('online')
        else:
            self.online_button.set_text('offline')

        self._print_info()
        if self.mode == 'routes':
            self._print_routes()
        elif self.mode == 'neighbors':
            self._print_neighbors()
        elif self.mode == 'inbox':
            self._print_inbox()
        elif self.mode == 'stats':
            self._print_stats()
        return super().update(time_delta)

class Controller(UIPanel):
    def __init__(self, parent):
        super().__init__(pg.Rect(cfg.GUI_DIM), manager=parent.manager)

        self.parent = parent
        self.manager = parent.manager
        self.settings = parent.settings
        self.nodes = parent.nodes
        self.signals = parent.signals

        self.ping_button = Button(self, 'ping', self.send_ping, 0, 0)
        self.reset_button = Button(self, 'reset', self.parent.reset_nodes, 0, 1)
        self.default_button = Button(self, 'default', lambda:self.parent.reset_nodes(default_settings=True), 0, 2)

        self.signals_status = StatusBar(self, 'signals', 6, 2, self.signals.__len__)   

        self.refresh()     
    
    def send_ping(self):
        s = self.settings.sender
        r = self.settings.recver        
        self.parent.name2node[s].aodv.send(self.parent.name2addr[r], 'ping')
        return True
    
    def set_num_nodes(self, num_nodes):
        self.settings.sender = cfg.NODE_NAMES[0]
        self.settings.recver = cfg.NODE_NAMES[0]
        self.settings.num_nodes = num_nodes
        self.parent.reset_nodes()
    
    def refresh(self):
        try:
            self.range_slider.kill()
            self.num_nodes_slider.kill()
        except Exception as e:
            log.debug(f'SIM:{e}')
        self.range_slider = Slider(self, 'range', (cfg.MIN_RANGE,cfg.MAX_RANGE), self.settings.range, lambda v: self.settings.__setattr__('range', v), 6, 0)
        self.num_nodes_slider = Slider(self, 'nodes', (3,len(cfg.NODE_NAMES)), self.settings.num_nodes, self.set_num_nodes, 6, 1)

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
        self.send_view = NodeViewer(self, 'sender', 0)
        self.recv_view = NodeViewer(self, 'recver', 1)

        self.reset_nodes()
    
    # def _update_active_nodes(self):
    #     data = {'user_type': gui.UI_BUTTON_PRESSED,
    #             'ui_element': selection_list.item_list_container.elements[0]}
    #     event = pg.event.Event(pg.USEREVENT, {})
    
    def randomize(self, side='left'):
        if side in ['left', 'send', 'sender', 'both']:
            old = self.settings.sender
            self.settings.sender = choice(cfg.NODE_NAMES[:self.settings.num_nodes])
            while (self.settings.sender == self.settings.recver or
                   self.settings.sender == old):
                self.settings.sender = choice(cfg.NODE_NAMES[:self.settings.num_nodes])
            self.send_view.refresh()
        
        if side in ['right', 'recv', 'recver', 'both']:
            old = self.settings.recver
            self.settings.recver = choice(cfg.NODE_NAMES[:self.settings.num_nodes])
            while (self.settings.recver == self.settings.sender or
                   self.settings.recver == old):
                self.settings.recver = choice(cfg.NODE_NAMES[:self.settings.num_nodes])
            self.recv_view.refresh()
        
    
    def reverse_direction(self):
        tmp = self.settings.sender
        self.settings.sender = self.settings.recver
        self.settings.recver = tmp
        self.send_view.refresh()
        self.recv_view.refresh()

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
                    if node.online and distance < signal.radius:
                        if not node.addr in signal.collided:
                            signal.collided.append(node.addr)
                            node.aodv.on_recv(signal.payload)
    
    # generate random nodes
    def reset_nodes(self, default_settings=False):
        if default_settings:
            self.settings.default()
            self.ctl.refresh()
        self.name2addr = {}
        self.addr2name = {}
        self.name2node = {}
        # clear old stuff
        self.nodes.empty()
        self.signals.empty()
        self.sim_surf.fill(pg.Color(cfg.SIM_COLOR))
        # create some nodes
        for n in cfg.NODE_NAMES[:self.settings.num_nodes]:
            x = randint(cfg.SIM_X_MARGIN, cfg.SIM_WIDTH - cfg.SIM_X_MARGIN)
            y = randint(cfg.SIM_Y_MARGIN, cfg.SIM_HEIGHT - cfg.SIM_Y_MARGIN)
            addr = randbytes(8)
            node = SimNode(self, addr, n, (x,y))
            self.nodes.add(node)
            self.name2addr[n] = addr
            self.addr2name[addr] = n
            self.name2node[n] = node

    def run(self):
        while self.running:
            # lock fps
            dt = self.clock.tick(cfg.FPS) / 1000.0

            # event loops
            events = pg.event.get()
            for event in events:
                if event.type == pg.QUIT:
                    self.running = False

                # keyboard shortcuts
                if event.type == pg.KEYDOWN:
                    # esc
                    if event.key == pg.K_ESCAPE:
                        self.running = False
                    # pause
                    if event.key == pg.K_SPACE:
                        self.settings.paused = not self.settings.paused
                    # default settings
                    if event.key == pg.K_d:
                        # self.settings.default()
                        self.reset_nodes(default_settings=True)
                    # reset
                    if event.key == pg.K_r:
                        self.reset_nodes()
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
                        self.randomize('left')
                        self.randomize('right')
                    # randomize recver
                    if event.key == pg.K_e:
                        self.randomize('right')
                    # toggle sender online
                    if event.key == pg.K_z:
                        self.name2node[self.settings.sender].toggle_online()
                    # toggle recver online
                    if event.key == pg.K_x:
                        self.name2node[self.settings.recver].toggle_online()

                self.manager.process_events(event)
            
            # update gui
            self.manager.update(dt)
            

            if not self.settings.paused:
                # logical stuff
                self.signals.update()
                self.nodes.update(events)
                self.detect_collisions()

                # graphical stuff
                self.screen.blit(self.sim_surf, (0, 0))
                self.sim_surf.fill(cfg.SIM_COLOR)
                self.nodes.draw(self.sim_surf)
                for s in self.signals:
                    s.draw(self.sim_surf)
                for n in self.nodes:
                    n.draw_address(self.screen)
            
            # draw gui
            self.manager.draw_ui(self.screen)
                
            pg.display.update()

if __name__ == '__main__':
    sim = Simulation()
    sim.run()