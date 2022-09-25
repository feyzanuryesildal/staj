from past.builtins import raw_input

from ConvertCocotoPascalXML import coco2voc
from ConvertCocotoYolo import convert_coco_json_to_yolo_txt

print("1- Convert COCO JSON to YOLO Darknet TXT")
print("2- Convert COCO JSON to Pascal VOC XML")
print("3- Convert COCO JSON to Tensorflow TFRecord")
r = raw_input("Yapmak istediğiniz işlemin numarsını yazın: ")
r = float(r)
if( r== 1):
    print( "1 çalıştı!")
    convert_coco_json_to_yolo_txt("output", "labels.json")
elif(r == 2 ):
    print( "2 çalıştı!")
    coco2voc(ann_file='labels.json', output_dir='output2')
elif( r==3):
    print( "3 çalıştı!")

    output_json_dict = {
        "images": [],
        "type": "instances",
        "annotations": [],
        "categories": []
    }
