bl_info = {
    "name": "Color Pallet from Image",
    "author": "Masato Suemura",
    "blender": (2, 80, 0),
    "version": (1, 0, 0), # test
    "location": "UV/Image Editor and View Layers",
    "category": "Render",
    "description": "export gif image file",
    "warning": "",
    "support": 'TESTING',
    # "wiki_url": "https:///",
    # "tracker_url": "https://"
}

import bpy
import os, os.path, sys, subprocess
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
import numpy as np
import scipy.cluster

class CPI_OT_InstallPillow(bpy.types.Operator):
    bl_idname = "cpi.install_pillow"
    bl_label = "install pillow"
    bl_options = {"REGISTER", "UNDO"}
    mode = StringProperty()

    def check_installed_package(self, context, python_dir):
        # get installed package
        packages_message = subprocess.check_output(".\python.exe -m pip freeze", shell=True)
        package_message_list = packages_message.decode().split("\n")
        package_list = []
        for p in package_message_list:
            package_name = p.replace("\r", "")
            package_name = package_name.split("==")[0]
            package_list.append(package_name)
        print(package_list)

        if "Pillow" in package_list:
            context.scene["pillow_status"] = "Installed!"
            return True
        else:
            context.scene["pillow_status"] = "Not Installed."
            return False

    def execute(self, context):
        # python.exeのパスを取得
        blender_version = str(bpy.app.version_string)[:4]
        blender_pass = str(sys.executable)
        python_dir = os.path.dirname(blender_pass) +"\\"+blender_version+ "\\python\\bin\\"
        python_pass = python_dir + "python.exe"
        os.chdir(python_dir)
        pip_install_command = ".\python.exe -m pip install pillow"
        pip_uninstall_command = ".\python.exe -m pip uninstall pillow"

        installed = False
        if self.mode == "CHECK":
            installed = self.check_installed_package(context, python_dir)
        elif self.mode == "INSTALL":
            subprocess.call(pip_install_command, shell=True)
        elif self.mode == "UNINSTALL":
            subprocess.call(pip_uninstall_command, shell=True)
        return {"FINISHED"}


class CPI_PT_preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    bpy.types.Scene.pillow_status = bpy.props.StringProperty(name = "", default="Please Check.")
    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.label(text="initial settings : ")
        row = layout.row(align=True)
        row.operator("cpi.install_pillow", text="check").mode = "CHECK"
        row.prop(scene, "pillow_status", text="")
        layout.operator("cpi.install_pillow", text="install pillow package").mode = "INSTALL"
        layout.label(text="If you want to uninstall the library, please show the console", icon="ERROR")
        layout.operator("cpi.install_pillow", text="uninstall pillow package").mode = "UNINSTALL"


class CPI_OT_ColorPicker(bpy.types.Operator):
    bl_idname = "cpi.color_picker"
    bl_label = "color picker"
    bl_options = {"REGISTER", "UNDO"}
    mode = StringProperty()

    def color_picker_kmeans(self, context, img):
        scene = context.scene
        img_small = img.resize((100, 100))
        color_arr = np.array(img_small)
        w_size, h_size, n_color = color_arr.shape
        color_arr = color_arr.reshape(w_size * h_size, n_color)
        color_arr = color_arr.astype(np.float)

        codebook, distortion = scipy.cluster.vq.kmeans(color_arr, scene["cpi_cluster"])
        code, _ = scipy.cluster.vq.vq(color_arr, codebook)

        n_data = []
        for n in range(scene["cpi_cluster"]):
            n_data.append(len([x for x in code if x == n]))
        desc_order = np.argsort(n_data)[::-1]
        print(codebook)
        return codebook
        # return ['#{:02x}{:02x}{:02x}'.format(*(codebook[elem].astype(int))) for elem in desc_order]

    def new_color_ramp(self, context, color_list, active_node_tree):
        scene = context.scene
        # カラーランプ作成
        color_ramp = active_node_tree.nodes.new(type="ShaderNodeValToRGB")
        print(color_list)

        if scene["cpi_cluster"] == 1:
            R = color_list[0][0] / 100.0
            G = color_list[0][1] / 100.0
            B = color_list[0][2] / 100.0
            print("{}{}{}".format(R, G, B))
            color_ramp.color_ramp.elements.remove(color_ramp.color_ramp.elements[0])
            color_ramp.color_ramp.elements[0].color = (R, G, B, 1)
        elif scene["cpi_cluster"] == 2:
            R = color_list[0][0] / 100.0
            G = color_list[0][1] / 100.0
            B = color_list[0][2] / 100.0
            # print('#{}{}{}'.format(hex(R), hex(G), hex(B)))
            print("{}{}{}".format(R, G, B))
            color_ramp.color_ramp.elements[0].color = (R, G, B, 1)
            R = color_list[1][0] / 100.0
            G = color_list[1][1] / 100.0
            B = color_list[1][2] / 100.0
            # print('#{}{}{}'.format(hex(R), hex(G), hex(B)))
            print("{}{}{}".format(R, G, B))
            color_ramp.color_ramp.elements[1].color = (R, G, B, 1)
        else:
            val = 1.0 / (len(color_list)-1)
            for i, color_code in enumerate(color_list):
                R = color_code[0] / 100.0
                G = color_code[1] / 100.0
                B = color_code[2] / 100.0
                if i == 0:
                    color_ramp.color_ramp.elements[0].color = (R, G, B, 1)
                elif i == len(color_list) - 1:
                    color_ramp.color_ramp.elements[len(color_list) - 1].color = (R, G, B, 1)
                else:
                    new_stopper = color_ramp.color_ramp.elements.new(val * i)
                    new_stopper.color = (R, G, B, 1)


    def execute(self, context):
        import PIL

        scene = context.scene

        active_node_tree = context.active_object.active_material.node_tree
        active_node = active_node_tree.nodes.active
        active_node_type = active_node.type
        if active_node_type == "TEX_IMAGE":
            active_image = active_node.image
            active_image_fp = active_image.filepath

            pil_source = PIL.Image.open(active_image_fp)
            color_list = self.color_picker_kmeans(context, pil_source)

            self.new_color_ramp(context, color_list, active_node_tree)

        return {"FINISHED"}


class CPI_PT_tools(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_label = "collor pallet"
    bl_category = "collor pallet"

    # properties
    bpy.types.Scene.cpi_cluster = bpy.props.IntProperty(name="", default=1, min=1, max=10)


    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        # col.label(text="loop counts  (0 = infinite)")
        col.prop(context.scene, "cpi_cluster", text="Color number")
        col.operator("cpi.color_picker", text="pick!")
        # col.label(text="output_directory")

# クラスの登録
def register():
    for cls in classes:
        print("Register : " + str(cls))
        bpy.utils.register_class(cls)

# クラスの登録解除
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

# 登録するクラス
classes = [
    CPI_PT_preferences,
    CPI_PT_tools,
    CPI_OT_InstallPillow,
    CPI_OT_ColorPicker
]

if __name__ == '__main__':
    register()


