from random import randbytes, randint
import logging as log

from node import Node as AODVNode
from packet import AODVType
import sim_config as cfg

import pygame as pg
import pygame_gui as gui

# init
pg.init()
pg.display.set_caption('AODV SIM')

# pg surface stuff
screen = pg.display.set_mode((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))
bg_sim = pg.Surface((cfg.SCREEN_WIDTH,cfg.SIM_HEIGHT))
bg_sim.fill(pg.Color(cfg.SIM_COLOR))
bg_gui = pg.Surface((cfg.SCREEN_WIDTH,cfg.GUI_HEIGHT))
bg_gui.fill(pg.Color(cfg.GUI_COLOR))

# other pg stuff
clock = pg.time.Clock()
font = pg.font.Font(None, 24)
nodes = pg.sprite.Group()
signals = pg.sprite.Group()

# gui stuff
manager = gui.UIManager((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))
hello_button = gui.elements.UIButton(relative_rect=pg.Rect(cfg.SEND_BUTTON_POS, cfg.SEND_BUTTON_DIM),
                                            text='ping',
                                            manager=manager,)
# send_dropdown = gui.elements.UIDropDownMenu(name_strs, name_strs[0], relative_rect=pg.Rect((0,600,100,30)))
send_dropdown = gui.elements.UIDropDownMenu(cfg.NODE_NAMES, cfg.NODE_NAMES[0], relative_rect=pg.Rect(cfg.SEND_DROPDOWN_POS, cfg.NAME_DROPDOWN_DIM))
recv_dropdown = gui.elements.UIDropDownMenu(cfg.NODE_NAMES, cfg.NODE_NAMES[1], relative_rect=pg.Rect(cfg.RECV_DROPDOWN_POS, cfg.NAME_DROPDOWN_DIM))


# set up logger
log_fmt = '%(asctime)s:%(levelname)s:%(message)s'
log_datefmt = "%H:%M:%S"
log.basicConfig(level=10, format=log_fmt, datefmt=log_datefmt)

def get_signal_color(raw:bytes):
    if len(raw) < 24:
        return cfg.UNKNOWN_COLOR
    elif raw[16] == AODVType.RREQ: # rreq
        return cfg.RREQ_COLOR
    elif raw[16] == AODVType.RREP: # rrep
        return cfg.RREP_COLOR
    elif raw[16] == AODVType.RERR: # rerr
        return cfg.RERR_COLOR
    elif raw[16] == AODVType.HELLO: # hello
        return cfg.HELLO_COLOR
    elif raw[16] == AODVType.DATA: # hello
        return cfg.DATA_COLOR
    else:
        return cfg.UNKNOWN_COLOR

# node class
class SimNode(pg.sprite.Sprite):
    def __init__(self, addr, nickname, position):
        super().__init__(nodes)
        self.addr = addr
        self.nickname = nickname
        self.aodv = AODVNode(node_addr=self.addr, nickname=nickname)
        self.image = pg.Surface(cfg.NODE_SPRITE_DIM)
        self.image.fill(pg.Color(cfg.NODE_COLOR))
        self.rect = self.image.get_rect(center=position)
        self.addr_surf = font.render(self.aodv.whoami(), True, pg.Color(cfg.ADDR_COLOR))
    
    def emit_signal(self, payload=b'', color='red'):
        signals.add(Transmission(src_addr=self.addr, payload=payload, position=self.rect.center, color=color))
    
    def update(self):
        p = self.aodv.update()

        # get signal type for color
        if p:
            self.emit_signal(p, get_signal_color(p))
    
    def draw_address(self):
        addr_pos = self.rect.x, self.rect.y - 25
        screen.blit(self.addr_surf, addr_pos)
        
# signal class
class Transmission(pg.sprite.Sprite):
    def __init__(self, src_addr:bytes, payload:bytes, position:tuple, color:str='red', speed:int=cfg.DEFAULT_SPEED, range:int=cfg.DEFAULT_RANGE):
        super().__init__(signals)
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

def detect_collisions():
    global nodes
    global signals

    # Check for collisions
    for signal in signals:
        for node in nodes:
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
def reset_nodes():
    global nodes
    global signals
    global bg_sim
    # clear old stuff
    nodes.empty()
    signals.empty()
    bg_sim.fill(pg.Color(cfg.SIM_COLOR))
    # create some nodes
    for n in cfg.NODE_NAMES:
        x = randint(cfg.SIM_X_MARGIN, cfg.SCREEN_WIDTH - cfg.SIM_X_MARGIN)
        y = randint(cfg.SIM_Y_MARGIN, cfg.SIM_HEIGHT - cfg.SIM_Y_MARGIN)
        node = SimNode(cfg.NODE_NAME2ADDR[n], n, (x,y))
        nodes.add(node)

# main loop
def loop():
    
    running = True
    paused = False
    reset_nodes()
    # main loop
    while running:
        # update/lock fps
        dt = clock.tick(cfg.FPS) / 1000.0

        # update sender/recver
        active_sender = send_dropdown.selected_option
        active_recver = recv_dropdown.selected_option

        # process event queue
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running == False
            
            # key events can happen anytime
            elif event.type == pg.KEYDOWN:
                # esc key
                if event.key == pg.K_ESCAPE:
                    running = False
                if event.key == pg.K_r:
                    reset_nodes()
                if event.key == pg.K_p:
                    paused = not paused
                if event.key == pg.K_TAB:
                    send_dropdown.selected_option = active_recver
                    recv_dropdown.selected_option = active_sender
            
            # these events only do if unpaused
            if not paused:
                # handle click
                if event.type == pg.MOUSEBUTTONDOWN:
                    # handle click on node
                    for node in nodes:
                        if node.rect.collidepoint(event.pos):
                            # node.emit_signal()
                            node.aodv._send_rreq(cfg.NODE_NAME2ADDR[active_recver])
                            print(node.aodv)
                # handle ui interactions
                elif event.type == gui.UI_BUTTON_PRESSED:
                    if event.ui_element == hello_button:
                        log.info(f'{active_sender}>>>{active_recver}')
                        for node in nodes:
                            if node.nickname == active_sender:
                                #   node.aodv._send_rreq(cfg.NODE_NAME2ADDR[active_recver])
                                node.aodv.send(cfg.NODE_NAME2ADDR[active_recver], 'ping')
            
            manager.process_events(event)
        
        if not paused:
            # logic stuff here
            manager.update(dt)
            signals.update()
            nodes.update()
            detect_collisions()



            # graphics stuff here
            screen.blit(bg_sim, (0,0))
            screen.blit(bg_gui, (0,cfg.SIM_HEIGHT))
            nodes.draw(bg_sim)
            manager.draw_ui(screen)

            for signal in signals:
                signal.draw(screen)
            for node in nodes:
                node.draw_address()


            # end of loop
            pg.display.flip()

if __name__ == '__main__':
    loop()
    pg.quit()