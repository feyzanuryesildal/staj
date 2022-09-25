import cv2
import json
from os import listdir
from os.path import isfile, join


f=open('labels.json')
data=json.load(f)

images=data["images"] #json dosyasındaki 'images' ögesini okur
annotations=data["annotations"] #json dosyasındaki 'annotations' ögesini okur

pathref = "C:\\Users\\feyza\\PycharmProjects\\pythonProjectStaj\\data\\"
onlyfiles = [f for f in listdir(pathref) if isfile(join(pathref, f))]

dosyaYolu = []
dosyaYolu2 = []

listAn = []
sayac2 = 0

imageIDlist =[]
imageIDlist2 =[]

categoryList = ["0",
        "person",
        "bicycle",
        "car",
        "motorcycle",
        "airplane",
        "bus",
        "train",
        "truck",
        "boat",
        "traffic light",
        "fire hydrant",
        "12",
        "stop sign",
        "parking meter",
        "bench",
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "elephant",
        "bear",
        "zebra",
        "giraffe",
        "26",
        "backpack",
        "umbrella",
        "29",
        "30",
        "handbag",
        "tie",
        "suitcase",
        "frisbee",
        "skis",
        "snowboard",
        "sports ball",
        "kite",
        "baseball bat",
        "baseball glove",
        "skateboard",
        "surfboard",
        "tennis racket",
        "bottle",
        "45",
        "wine glass",
        "cup",
        "fork",
        "knife",
        "spoon",
        "bowl",
        "banana",
        "apple",
        "sandwich",
        "orange",
        "broccoli",
        "carrot",
        "hot dog",
        "pizza",
        "donut",
        "cake",
        "chair",
        "couch",
        "potted plant",
        "bed",
        "66",
        "dining table",
        "68",
        "69",
        "toilet",
        "71",
        "tv",
        "laptop",
        "mouse",
        "remote",
        "keyboard",
        "cell phone",
        "microwave",
        "oven",
        "toaster",
        "sink",
        "refrigerator",
        "83",
        "book",
        "clock",
        "vase",
        "scissors",
        "teddy bear",
        "hair drier",
        "toothbrush"]

#data klasöründeki resimlerin yollarını verir
def listDosyaYolu():
    for i in images:
        for jk in [i['id']]:
            for im in annotations:
                for j in [im['image_id']]:
                    if (j == jk):
                        #bbocCountAn = bbocCountAn + 1
                        for j in [i['file_name']]:
                            for m in onlyfiles:
                                if (m == j):
                                    res = pathref + m
                                    dosyaYolu.append(str(res))
                            #sayac2 = sayac2 + 1
            #listAn.append(bbocCountAn)
    for i in dosyaYolu:
        if i not in dosyaYolu2:
            dosyaYolu2.append(i)
    return dosyaYolu2

#json dosyasındaki image lerin idlerini listeler
def listImageID():
    for i in images:
        for jk in [i['id']]:
            for im in annotations:
                for j in [im['image_id']]:
                    if (j == jk):
                        #print(j)
                        imageIDlist.append(jk)
    for i in imageIDlist:
        if i not in imageIDlist2:
            imageIDlist2.append(i)
    return imageIDlist2

#her resme ailt kaçtane bbox olduğunu liste içinde tutuyor
def listAnCount():
    for i in images:
        for jk in [i['id']]:
            bbocCountAn = 0;
            for im in annotations:
                for j in [im['image_id']]:
                    if (j == jk):
                        bbocCountAn = bbocCountAn + 1

            listAn.append(bbocCountAn)
    return listAn
catName=[]
#gönderilen resmin id sine göre bboxlarını döndürüyor.
#bboxCount da diziyi oluşturmak için aldık.
def listBbox(imageId,bboxCount):
    count = 0
    listBbox = [[0 for x in range(4)] for y in range(bboxCount)]
    for im in annotations:
        for j in [im['image_id']]:
            if(imageId == j):
                for i in range(4):
                    listBbox[count][i] = int(im['bbox'][i])
                count = count + 1
    return listBbox

#id si gönderilen resmin annotation idsini döndürür
def founAnnotationId(bbox):
    for im in annotations:
        for j in [im['bbox']]:
            if ((bbox[0] == int(j[0])) & (bbox[1] ==int( j[1])) & (bbox[2] == int(j[2])) & (bbox[3] == int(j[3]))):
                return im['id']


#annotationun id sini alıp categori numarasını döndürür
def foundCategoryId(id):
    for im in annotations:
        for j in [im['id']]:
            if (id == j):
                return im['category_id']



imgCount = 0
for i in listDosyaYolu():
    resim = cv2.imread(i)
    count = 0

    while count < listAnCount()[imgCount]:
        list = listBbox(listImageID()[imgCount],listAnCount()[imgCount])
        p0 = int(list[count][0])
        p1 = int(list[count][1])
        p2 = int(list[count][2])
        p3 = int(list[count][3])
        cv2.rectangle(resim, (int(p0), int(p1)),
                      (int(p2) + int(p0), int(p3) + int(p1)), (0, 255, 0),
                      1)
        anId = founAnnotationId(list[count])
        category = foundCategoryId(anId)
        #cv2.putText(resim, categoryList[category], (p0, p1), cv2.FONT_HERSHEY_DUPLEX, 1, (255, 255, 255, 255),1, cv2.LINE_AA) #bbox bilgisini fotoğrafın üstüne yazar
        count = count + 1
    imgCount = imgCount + 1
    cv2.imshow("res", resim)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

