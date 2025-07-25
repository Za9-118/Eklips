## Import all the libraries
import pyglet as pg
import json, time, types, tkinter as tk
from tkinter.messagebox import *
from classes import Event, UI, Resources
from pyglet import gl
from pyglet.graphics.shader import Shader, ShaderProgram
from pyglet.text import Label as PygletLabel
from anytree import NodeMixin
from PIL import Image, ImageTk

## Scene class
class Scene:
    def __init__(self, file, screen, resourceman, Data):
        self.file            = file
        self.eng_globals     = {}
        self.player_global   = pg.media.Player()
        self.nodes           = {}
        self.cam_pos         = [0, 0]
        self.Data            = Data
        self.killing         = 0
        self.nodes_collision = {}
        self.properties      = {}
        self.screen          = screen
        self.resourceman     = resourceman # Resource manager
        self.load() 
    
    def empty(self):
        self.nodes_collision = {}
        self.cam_pos         = [0, 0]
        for i in self.nodes:
            self.nodes[i]["object"].discard()
        self.nodes           = {}
    
    def add_node(self, who, where, parameters={}, script=None, node_data={}, name="Node?"):
        id = len(self.nodes)

        # Full path including this node
        full_path   = f"{where}/{name}".strip("/")

        directories  = full_path.split("/")[:-1]  # Only parents, exclude self
        parent       = None
        current_path = ""

        for directory in directories:
            existing = self.get_node_from_path(current_path.lstrip("/"), directory)
            current_path += f"/{directory}"
            if not existing:
                raise Exception("The node you are trying to create's parent does not exist.")
            else:
                parent = existing

        # Create the actual node
        classobj = globals().get(who)
        object = classobj.__new__(classobj)
        object.project_data = self.Data
        object.__init__(parameters, parent, self.Data, script, self.screen, self.resourceman, self, where, name, self.eng_globals)
        object.on_ready()

        # Store in flat dictionary
        self.nodes[id] = {
            "class": who,
            "path": where,
            "object": object,
            "name": name,
            "base_data": node_data
        }

    def save(self, save_as="myself"):
        # Serialize
        serialized = {
            "Properties": self.properties,
            "Nodes": {}
        }

        for node in self.nodes:
            node_info = self.nodes[node]
            data = {
                "script_properties": {},
                "name":              node_info["object"].name,
                "script":            node_info["object"].script,
                "script":            node_info["path"],
                "runtimedata":       node_info["object"].runtime_data,
                "type":              node_info["class"],
                "properties":        node_info["object"].properties,
            }

            serialized[str(node)] = data
        
        # Save data
        if save_as == "myself":
            save_as = self.file
        with open(save_as, "w") as f:
            f.write(json.dumps(serialized, indent=4))

    def load(self):
        self.nodes           = {}
        self.cam_pos         = [0, 0]
        self.nodes_collision = {}
        scene_obj  = json.loads(self.resourceman.load(self.file).get())
        self.properties = scene_obj["Properties"]
        for node in scene_obj["Nodes"]:
            node_data = scene_obj["Nodes"][node]
            self.add_node(node_data["type"], node_data["path"], node_data["properties"], node_data["script"], node_data, node_data["name"])

    def update(self, signalclass, glob):
        try:
            for nodeID in self.nodes:
                if not self.killing:
                    node            = self.nodes[nodeID]["object"]
                    node.engine_glb = glob
                    node.update()
                    if "signals" in node.demand_for:
                        node.signal_data = {
                            "data": signalclass.get(),
                            "clss": signalclass
                        }
                    node.demand_for = []
        except Exception as error:
            print(f" Scene({self.file}) had an error updating; {error}")
            raise error
    
    def get_node_from_name(self, name):
        # All names must be unique for this to work.
        for i in self.nodes:
            if self.nodes[i]["object"].name == name:
                return self.nodes[i]["object"]
    
    def get_node_id_from_name(self, name):
        # All names must be unique for this to work.
        for i in self.nodes:
            if self.nodes[i]["object"].name == name:
                return i
    
    def get_node_from_path(self, path, name):
        for i in self.nodes:
            if self.nodes[i]["path"] == path:
                if self.nodes[i]["name"] == name:
                    return self.nodes[i]["object"]

## Nodes (ROOT NODES)
class Node(NodeMixin):
    """
    ## An empty Node.

    Nodes are the building block of Eklips (well, Eklips 4+ atleast). Every Node is inherited off this node class.
    A tree of Nodes make a Scene, A node is stored as `myself.root_scene` or `scene`.

    All Nodes must have an unique name.

    The `myself` value is.. the node the script is attached to. You cannot replace Node functions with a script.
    
    You can make a script have an `on_ready(empty)` function. This will only run when a Node is fully loaded.
    You can make a script have an `_process(empty)` function. This will run every frame after `on_ready(empty)`.

    There is nothing to do with it. The only useful thing to do with it is run a script with it, and no more.
    """
    def __init__(self, parameters, parent, data, script, screen, resourceman, scene_obj, where, name, eng_global):
        self.screen       = screen
        self.parameters   = {}
        self.project_data = data
        self.added_param  = parameters
        self.runtime_data = {}
        self.node_path_da = where
        self.name         = name
        self.parent       = parent
        self.signal_data  = {}
        self.demand_for   = []
        self.root_scene   = scene_obj
        self.script       = script
        self.window_id    = "main"
        self.camera_pos   = [0,0]
        self.dead         = 0
        self.where        = where
        self.resourceman  = resourceman
        self.editor_icon  = "Node"
        self.initialized  = False
        self.engine_glb   = eng_global
        self.scriptobj    = 0
        self.true_init()
        for i in self.added_param:
            self.parameters[i] = self.added_param[i]
        self.initialized  = True
    
    def true_init(self):
        # Empty
        pass

    def on_ready(self):
        # Empty
        pass

    def true_update(self):
        # Empty
        pass

    def call_deferred(self, fun, args=[]):
        try:
            func = types.MethodType(self.scriptobj[fun], self)
            if len(args): func(*args)
            else: func()
        except Exception as e:
            print(f"Unable to call {type(self).__name__}.{fun}{tuple(args)}: {e}")
            raise e

    def run_script(self):
        if self.script:
            if not self.scriptobj:
                myglb=self.engine_glb
                myglb["myself"] = self
                exec(self.resourceman.load(self.script).get(), globals=myglb,locals=myglb)
                self.scriptobj=myglb
                self.call_deferred("on_ready")
            else:
                self.call_deferred("_process")

    def update(self):
        if not self.dead:
            self.get_fired()
            self.run_script()
            self.true_update()
        else:
            self._discard()
    
    def _discard(self):
        del self.parameters
        del self.name
        del self.runtime_data
        del self.scriptobj
        del self.script
        self.initialized = False
        del self
    
    def discard(self):
        self.dead = 1
    
    def get_fired(self):
        self.demand_for.append("signals")

class TkWindow(Node):
    """
    ## A Tkinter Window.

    Self-explanatory if you have used Tkinter. `TkWindow.tk_self` is the Tk() object.
    No 2D Nodes work in this. The icon property only works if the image is in res://.
    """
    def true_init(self):
        self.tk_self = tk.Tk()
        self.parameters["dimension"]  = "640x480"
        self.parameters["caption"]    = "Window.Tk"
        self.parameters["icon"]       = "res://media/icon.png"
        self.parameters["fullscreen"] = 0
        
    def on_ready(self):
        self.tk_self.geometry(self.parameters["dimension"])
        self.tk_self.title(self.parameters["caption"])
        icon_image  = Image.open(self.parameters["icon"].replace("res://", self.project_data.data_directory+"/"))
        photo_image = ImageTk.PhotoImage(icon_image)
        self.tk_self.wm_iconphoto(True, photo_image)

class OptionDialog(TkWindow):
    """
    ## A Window node to ask for a question.
     
    The `OptionDialog.fate` value is a boolean, It returns True if the user chose an affirmative values.

    The questions that can be asked are:
    # 1: Yes/No
    # 2: Ok/Cancel
    # 3: Retry/Cancel
    # 4: Yes/No/Cancel
    """

    def true_init(self):
        self.parameters["caption"]     = "Node.Window.Tk.Dialog"
        self.parameters["icon"]        = "res://media/icon.png"
        self.parameters["message"]     = "Node.Window.Tk.Dialog.Message"
        self.parameters["optionindex"] = 4
        self.parameters["custom_opts"] = []
        self.fate                      = 0
    
    def on_ready(self):
        return
    
    def popup(self):
        if self.parameters["optionindex"] == 1:
            func=askyesno(self.parameters["caption"], self.parameters["message"])
        if self.parameters["optionindex"] == 2:
            func=askokcancel(self.parameters["caption"], self.parameters["message"])
        if self.parameters["optionindex"] == 3:
            func=askretrycancel(self.parameters["caption"], self.parameters["message"])
        if self.parameters["optionindex"] == 4:
            func=askyesnocancel(self.parameters["caption"], self.parameters["message"])
        self.fate = func
        return self.fate

class AudioPlayer(Node):
    """
    ## A Media Node to play audio.
     
    Self-explanatory.
    """
    def true_init(self):
        self.player       = None
        self.parameters   = {
            "media":       "res://media/load.mp3",
            "loop":        False,
            "where":       0,
            "autostart":   False,
            "play_global": False
        }
        self.editor_icon  = "AudioPlayer"
        self.name         = "AudioPlayer"
        self.audio_data   = 0
        self.is_playedyet = 0
    
    def on_ready(self):
        global player_global
        if self.parameters["play_global"]: self.player = self.root_scene.player_global
        else:                              self.player = pg.media.Player()
    
    def play(self, volume=1):
        what = self.audio_data
        if not what:
            what = self.resourceman.load(self.parameters["media"]).get()
        self.player.queue(what)
        self.player.volume = volume
        self.player.play()

    def pause(self):
        self.player.pause()
    
    def update(self):
        global camera_pos
        if not self.dead:
            if not self.is_playedyet and self.parameters["autostart"]:
                self.play()
                self.is_playedyet = 0
            self.get_fired()
            self.run_script()
            self.true_update()
        else:
            self._discard()

class VideoPlayer(AudioPlayer):
    """
    ## A Media Node to render video and play it's audio.
     
    Self-explanatory.
    """
    def true_init(self):
        self.player       = None
        self.parameters   = {
            "media":     "res://media/load.mp3",
            "loop":      0,
            "where":     0,
            "autostart": 0
        }
        self.name         = "VideoPlayer"
        self.audio_data   = 0
        self.as_playedyet = 0
        self.editor_icon  = "VideoPlayer"
        self.parameters["transform"]  = {
            "scale":  [1,1],
            "pos":    [0,0],
            "anchor": "top left",
            "layer":  0,
            "alpha":  1,
            "scroll": [0,0]
        }
        self.runtime_data["rendererpos"] = self.parameters["transform"]["pos"]
    
    def update(self):
        global camera_pos
        if not self.as_playedyet:
            self.play()
            self.as_playedyet = 0
        if self.player.playing:
            self.screen.blit(
                pg.sprite.Sprite(
                    self.player.texture
                ),                                   
                self.runtime_data["rendererpos"],             
                anchor  = self.parameters["transform"]["anchor"],
                scale   = self.parameters["transform"]["scale"],
                layer   = self.parameters["transform"]["layer"],
                rot     = self.parameters["transform"]["rot"],
                opacity = self.parameters["transform"]["alpha"],
                scroll  = self.parameters["transform"]["scroll"]
            )
        self.get_fired()
        self.run_script()
        self.runtime_data["rendererpos"] = [
            self.parameters["transform"]["pos"][0] + camera_pos[0],
            self.parameters["transform"]["pos"][1] + camera_pos[1]
        ]
        self.true_update()

class CanvasItem(Node):
    """
    ## A Canvas Node.
    
    This is a Node that has parameters for transformation, and is meant for rendering items in a canvas.
    This has no properties for Cameras, which makes it good for rendering UI elements. Which is it's purpose.
    For Nodes in a 2D world, use Node2D.

    This has relativity only on the position and anchor.
    """
    def true_init(self):
        self.parameters["transform"] = {
            "scale":  [1,1],
            "pos":    [0,0],
            "anchor": "top left",
            "layer":  0,
            "alpha":  1,
            "size":   [100, 100],
            "scroll": [0, 0],
            "rot":    0
        }
        self.sprid                       = 0
        self.parameters["visible"]       = 1
        self.name                        = "CanvasItem"
        self.anchor                      = self.parameters["transform"]["anchor"]
        self.editor_icon                 = "CanvasItem"
        self.runtime_data["rendererpos"] = self.parameters["transform"]["pos"][:]
        self.runtime_data["relativepos"] = self.parameters["transform"]["pos"][:]

    def get_relative_pos(self):
        my_pos     = self.parameters["transform"]["pos"]
        parent_pos = [0, 0]
        if self.parent and hasattr(self.parent, "get_relative_pos"):
            parent_pos = self.parent.get_relative_pos()[0]
            return [my_pos[0] + parent_pos[0], my_pos[1] + parent_pos[1]], parent_pos
        return my_pos[:], parent_pos
    
    def get_relative_anchor(self):
        if self.parent and hasattr(self.parent, "anchor"):
            return self.parent.parameters["transform"]["anchor"]
        return self.parameters["transform"]["anchor"]
    
    def _discard(self):
        # self.screen.rem_from_pool(self.sprid)
        del self.parameters
        del self.name
        del self.runtime_data
        del self.scriptobj
        del self.script
        self.initialized = False
        del self
    
    def load_render(self):
        if self.image and self.parameters["visible"]:
            self.sprid = self.screen.blit(
                self.image,                                   
                self.runtime_data["rendererpos"],             
                anchor  = self.parameters["transform"]["anchor"],
                scale   = self.parameters["transform"]["scale"],
                layer   = self.parameters["transform"]["layer"],
                rot     = self.parameters["transform"]["rot"],
                opacity = self.parameters["transform"]["alpha"],
                scroll  = self.parameters["transform"]["scroll"]
            )
    
    def get_if_mouse_hovering(self):
        mpos = self.screen.mpos
        is_it = (
            mpos[0] < self.parameters["transform"]["pos"][0] + self.parameters["transform"]["size"][0] and
            mpos[0] + 20 > self.parameters["transform"]["pos"][0]                                      and
            mpos[1] < self.parameters["transform"]["pos"][1] + self.parameters["transform"]["size"][1] and
            mpos[1] + 20 > self.parameters["transform"]["pos"][1]
        )
        return is_it
    
    def update(self):
        global camera_pos
        if not self.dead:
            self.get_fired()
            self.run_script()
            self.anchor                      = self.parameters["transform"]["anchor"]
            rel_pos, parent_pos              = self.get_relative_pos()

            # World-space relative position
            self.runtime_data["relativepos"] = rel_pos
            self.runtime_data["rendererpos"] = rel_pos
            print(f"{self.name} // Rel: {rel_pos} // Mom: {parent_pos} // Cam: ?? // RendPos: {self.runtime_data["rendererpos"]}")
            self.true_update()
        else:
            self._discard()

class Node2D(CanvasItem):
    """
    ## A 2D Node.
    
    This is basically the same as a CanvasItem, but meant for gameplay purposes, because it follows the camera.
    All nodes that are meant in a 2D space (Camera2D, Sprite2D..) are inherited from this Node.
    """

    def true_init(self):
        super().true_init()
        self.name         = "Node2D"
        self.editor_icon  = "Node2D"
    
    def update(self):
        global camera_pos
        if not self.dead:
            self.get_fired()
            self.run_script()
            self.anchor                      = self.parameters["transform"]["anchor"]
            rel_pos, parent_pos              = self.get_relative_pos()

            # World-space relative position
            self.runtime_data["relativepos"] = rel_pos
            cam = self.root_scene.cam_pos
            self.runtime_data["rendererpos"] = [rel_pos[0] - cam[0], rel_pos[1] - cam[1]]
            print(f"{self.name} // Rel: {rel_pos} // Dad: {parent_pos} // Cam: {cam} // RendPos: {self.runtime_data["rendererpos"]}")
            self.true_update()
        else:
            self._discard()

## Every canvas node
class Label(CanvasItem):
    """
    ## A Canvas Node to render text.
     
    Self-explanatory.
    """
    def true_init(self):
        super().true_init()
        self.name = "Label"
    
    def load_render(self):
        if self.parameters["visible"]:
            pos = self.runtime_data["rendererpos"]
            print(pos)
            self.screen.render(
                text    = self.parameters["text"],
                pos     = pos,

                anchor  = self.anchor,
                layer   = self.parameters["transform"]["layer"],
                blit_in = self.window_id
            )
    
    def true_update(self):
        self.load_render()
        

class RichLabel(Label):
    """
    ## A Label Node to render fancy text.
     
    Self-explanatory.
    """
    pass

class ColorRect(CanvasItem):
    """
    ## A Canvas Node to render a colored Rectangle.
     
    Self-explanatory.
    """
    def true_init(self):
        super().true_init()
        self.name = "ColorRect"
        self.parameters["color"] = [128,128,128]
        self.image               = 0

    def true_update(self):
        self.load_render()

    def on_ready(self):
        r, g, b = self.parameters["color"]
        # RGB for each pixel, repeated for all pixels
        raw_data = bytes([r, g, b] * self.parameters["transform"]["size"][0] * self.parameters["transform"]["size"][1])
        self.image = Resources.Image(
            data = pg.image.ImageData(
                self.parameters["transform"]["size"][0],
                self.parameters["transform"]["size"][1],
                'RGB',
                raw_data
            ),
            type = "sprite",
            path = f"{r+g+b/3}{self.parameters["transform"]["size"]}.mm"
        )

class Button(ColorRect):
    def true_init(self):
        super().true_init()
        self.name = "Button"
        self.parameters["color"] = [128,128,128]
        self.clicked             = False
        self.image               = 0
    
    def true_update(self):
        hovering = self.get_if_mouse_hovering()
        clicked  = self.screen.mclk[0]            

        self.clicked = (hovering and clicked)
        
        if not self.clicked:
            self.load_render()
        self.screen.render(
            self.parameters["text"],
            [
                self.runtime_data["rendererpos"][0]+7.5,
                self.runtime_data["rendererpos"][1]
            ],
            anchor=self.parameters["transform"]["anchor"]
        )

class Treeview(CanvasItem):
    # TODO: Make visually pleasing
    def true_init(self):
        super().true_init()
        self.name = "Treeview"
        self.treechildren = {}
        self.revealed     = []
    
    def _rlayer(self, data, pos=[0,0], layer = 0):
        id        = 0
        _pos      = pos.copy()
        for i in data:
            node_p    = f"{self.node_path_da}/{self.name}"
            nm        = f"Label{id}"
            _have_kid = "v " if len(data[i]) else ""
            self.screen.render(
                text    = f"{'| '*layer}{_have_kid}{i}",
                pos     = _pos,
                anchor  = "",
                layer   = 10+id,
                blit_in = self.window_id
            )
            id      += 1
            _pos[1] += 25
            _pos     = self._rlayer(data[i], _pos, layer+1)
        return _pos

    def true_update(self):
        # TBA
        self.treechildren = self.parameters["children"]
        self.revealed     = []
        
        if self.parameters["visible"]:
            self._rlayer(self.treechildren, self.runtime_data["rendererpos"].copy())

## Every other 2D node
class PhysicsBody2D(Node2D):
    def true_init(self):
        super().true_init()
        self.name = "PhysicsBody2D"
    
    def _phys_init(self):
        self._onf   = False
        self._onw   = False
        self.weight = 1
        self.motion = [0, 0]

    def if_on_floor(self): return self._onf 
    def if_on_wall(self):  return self._onw
    def _physics_update(self, nearby, collided, bounce_mode = False):
        # Most basic of basic physics.
        self._onf = False
        self._onw = False

        for i in collided:
            node = i
            if self.colliderect(node):
                # You little shit
                if self.parameters["transform"]["pos"][1] + self.parameters["transform"]["size"][1] <= node.parameters["transform"]["pos"][1]:
                    self._onf = True
                    # Ow
                    if bounce_mode:
                        self.motion[1] = -self.motion[1] / self.weight
                    else:
                        self.motion[1] = 0
                elif (self.parameters["transform"]["pos"][0] + self.parameters["transform"]["size"][0] > node.parameters["transform"]["pos"][0] and
                      self.parameters["transform"]["pos"][0] < node.parameters["transform"]["pos"][0] + node.parameters["transform"]["size"][0]):
                    self._onw = True
                    print("collided_")
                    # Ow
                    if bounce_mode:
                        self.motion[0] = -self.motion[0] / self.weight
                    else:
                        self.motion[0] = 0
            
        self.parameters["transform"]["pos"][0] += self.motion[0]
        self.parameters["transform"]["pos"][1] += self.motion[1]
        if bounce_mode:
            self.motion[1] = -self.motion[1]
        else:
            self.motion = [0,0]
        

class CollisionBox2D(PhysicsBody2D):
    def _check_overlap(self, rect1, rect2):
        # Use AABB
        return (
            rect1.parameters["transform"]["pos"][0] < rect2.parameters["transform"]["pos"][0] + rect2.parameters["transform"]["size"][0] and
            rect1.parameters["transform"]["pos"][0] + rect1.parameters["transform"]["size"][0] > rect2.parameters["transform"]["pos"][0] and
            rect1.parameters["transform"]["pos"][1] < rect2.parameters["transform"]["pos"][1] + rect2.parameters["transform"]["size"][1] and
            rect1.parameters["transform"]["pos"][1] + rect1.parameters["transform"]["size"][1] > rect2.parameters["transform"]["pos"][1]
        )

    def true_init(self):
        super().true_init()
        self._phys_init()
        self.name                                = "CollisionBox2D"                                 
        self.editor_icon                         = "CollisionBox2D"                                 
        self.remap_dim()
        self.id                                  = f"{self.path}/{self.name}NodeColA{self.w*self.h}"
        self.root_scene.nodes_collision[self.id] = self                                     
    
    def remap_dim(self):
        self.x,self.y,self.w,self.h = self.parameters["transform"]["pos"][0], self.parameters["transform"]["pos"][1], self.parameters["transform"]["size"][0], self.parameters["transform"]["size"][1]
    
    def colliderect(self, rect): return self._check_overlap(self, rect)

    def collidelist(self, rect_list):
        id = 0
        for i in rect_list:
            if self._check_overlap(self, i): return id
            else: id+=1
        return -1

    def collidelistall(self, rect_list):
        il = []
        for i in rect_list:
            if self._check_overlap(self, i): il.append(i)
        return il
    
    def get_all_rects_nearby(self, rang=500):
        il = []
        for i in self.root_scene.nodes_collision:
            node = self.root_scene.nodes_collision[i]
            # rang = The range in pixels that this rectangle can be in to count

            if node == self: continue

            if abs(node.x - node.x) < rang:
                if abs(node.y - node.y) < rang:
                    il.append(node)
        return il
    
    def true_update(self):
        global camera_pos
        self.remap_dim()
        nearby   = self.get_all_rects_nearby()
        collided = self.collidelistall(nearby)
        self._physics_update(nearby, collided)  # Update physics based on nearby rectangles and collided ones

    def _discard(self):
        del self.parameters
        del self.name
        del self.runtime_data
        del self.scriptobj
        del self.script
        self.initialized = False
        self.root_scene.nodes_collision.pop(self.id)
        del self

class Camera2D(Node2D):
    """
    ## A 2D Node to control the Camera in the 2D world.
     
    Self-explanatory. The position of this Node is the position of the camera
    """
    def true_init(self):
        super().true_init()
        self.editor_icon = "Camera2D"
        self.name        = "Camera2D"
    
    def true_update(self):
        self.root_scene.cam_pos = [
            self.parameters["transform"]["pos"][0] - self.screen.screen.width  // 2,
            self.parameters["transform"]["pos"][1] - self.screen.screen.height // 2,
        ]

class Sprite2D(Node2D):
    """
    ## A 2D Node to display an image.
     
    Self-explanatory.
    """
    def true_init(self):
        super().true_init()
        self.parameters["sprite"] = "res://media/bg.png"
        self.image                = 0
        self.editor_icon          = "Sprite2D"

    def on_ready(self):
        asset      = self.resourceman.load(self.parameters["sprite"])
        self.image = asset
    
    def true_update(self):
        self.load_render()

class AnimatedSprite2D(Sprite2D):
    """
    ## A 2D Node to display an image.
     
    Self-explanatory.
    """
    def true_init(self):
        super().true_init()
        self.parameters["sprite"] = ["res://media/bg.png"]
        self.images               = []
        self.sprite_used          = 0 
        self.editor_icon          = "AnimatedSprite2D"

    def on_ready(self):                     
        for i in self.parameters["sprite"]: 
            asset = self.resourceman.load(i)
            self.images.append(asset)       
    
    def load_render(self):
        if self.sprite_used in self.images and self.parameters["visible"]:
            self.screen.blit(
                self.images[self.sprite_used],                                   
                self.get_relative_pos(),             
                anchor  = self.parameters["transform"]["anchor"],
                scale   = self.parameters["transform"]["scale"],
                layer   = self.parameters["transform"]["layer"],
                rot     = self.parameters["transform"]["rot"],
                opacity = self.parameters["transform"]["alpha"],
                scroll  = self.parameters["transform"]["scroll"]
            )

class Parallax2D(Sprite2D):
    def true_init(self):
        super().true_init()
        self.parameters["sprite"]       = "res://media/bg.png"
        self.parameters["scroll_speed"] = 5
        self.image                      = 0
        self.editor_icon                = "Parallax2D"
    
    def true_update(self):
        self.load_render()
        self.parameters["transform"]["scroll"][0] -= self.parameters["scroll_speed"]
        if self.parameters["transform"]["scroll"][0] < (-self.image.get().width) + self.parameters["scroll_speed"]:
            self.parameters["transform"]["scroll"][0] = -(self.parameters["scroll_speed"])
        
