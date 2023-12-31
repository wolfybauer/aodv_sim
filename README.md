# aodv_sim

## description

- AODV routing simulation with [pygame](https://www.pygame.org) and [pygame_gui](https://pygame-gui.readthedocs.io/en/latest/quick_start.html).
- planning to implement IRL in micropython eventually, so limited python featureset

## instructions

### install
`pip3 install -r requirements.txt`

### run
- `python3 main.py`
- use gui to send data
- click node to see its contents
- press 'r' to reset random node positions

## status

### 2023-12-31

initial commit. not quite working yet
- sim:
 - click still just sends rreq
 - need implement show_node_contents() etc
- node.py:
 - logical errors and stuff yet unimplemented
 - structure getting there
- protocol-related:
 - ugly, clunky
 - ..stupid?
 - works for now