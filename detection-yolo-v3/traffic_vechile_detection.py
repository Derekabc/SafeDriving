"""
This module is built on the resposity: [Resposity Link](https://github.com/ayooshkathuria/YOLO_v3_tutorial_from_scratch).
"""

from __future__ import print_function, division
import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import torch
from torch.autograd import Variable
import cv2, os
from util import *
from darknet import Darknet
from preprocess import prep_image, inp_to_image, letterbox_image
from moviepy.editor import VideoFileClip
import random
import pickle as pkl
import argparse
import matplotlib.pyplot as plt

Focus_length = 28


def prep_image(img, inp_dim):
    """
    Prepare image for inputting to the neural network.
    Returns a Variable
    """

    orig_im = img
    dim = orig_im.shape[1], orig_im.shape[0]
    img = (letterbox_image(orig_im, (inp_dim, inp_dim)))
    img_ = img[:, :, ::-1].transpose((2, 0, 1)).copy()
    img_ = torch.from_numpy(img_).float().div(255.0).unsqueeze(0)
    return img_, orig_im, dim


def write(x, img):
    # img_dim = img.size(1)
    # c1 = tuple(x[1:3].int())
    # c2 = tuple(x[3:5].int())
    c1 = tuple(x[1:3].cpu().numpy().tolist())
    c2 = tuple(x[3:5].cpu().numpy().tolist())
    # print(int(c2[1]) - int(c1[1]))
    cls = int(x[-1])
    label = "{0}".format(classes[cls])

    color = random.choice(colors)
    # cv2.rectangle(img, c1, c2, color, 1)
    cv2.rectangle(img, (int(c1[0]), int(c1[1])), (int(c2[0]), int(c2[1])), color, 1)
    # put label on the image
    t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_PLAIN, 1, 1)[0]
    c3 = c1[0] + t_size[0] + 3, c1[1] + t_size[1] + 4
    # cv2.rectangle(img, c1, c3, color, -1)
    cv2.rectangle(img, (int(c1[0]), int(c1[1])), (int(c3[0]), int(c3[1])), color, 1)

    # cv2.putText(img, label, (c1[0], c1[1] + t_size[1] + 4), cv2.FONT_HERSHEY_PLAIN, 1, [225, 255, 255], 1)
    cv2.putText(img, label, (int(c1[0]), int(c1[1]) + t_size[1] + 4), cv2.FONT_HERSHEY_PLAIN, 1, [225, 255, 255], 1)

    if int(c2[1]) - int(c1[1]) == 0:
        pass
    else:
        distance = "{:.2f}".format(float(29 * Focus_length * 1.5 / (int(c2[1]) - int(c1[1]))))
        t_size_1 = cv2.getTextSize(distance, cv2.FONT_HERSHEY_PLAIN, 1, 1)[0]
        # right-top corner
        c_r = tuple([int(c2[0]), int(c1[1])])
        c4 = c_r[0] + t_size_1[0] + 4, c_r[1] + t_size_1[1] + 5
        cv2.rectangle(img, c_r, (int(c4[0]), int(c4[1])), color, -1)
        if 29 * Focus_length * 1.5 / (int(c2[1]) - int(c1[1])) <= 20:
            cv2.putText(img, distance, (c_r[0], c_r[1] + t_size_1[1] + 4), cv2.FONT_HERSHEY_PLAIN, 2, [225, 0, 0], 1)
        else:
            cv2.putText(img, distance, (c_r[0], c_r[1] + t_size_1[1] + 4), cv2.FONT_HERSHEY_PLAIN, 1, [225, 225, 225], 1)
    return img


def arg_parse():
    """
    Parse arguements to the detect module
    """
    parser = argparse.ArgumentParser(description='YOLO v3 Video Detection Module')
    parser.add_argument("--video", dest='video', help=
    "Video to run detection upon",default="out_project.mp4", type=str)
    parser.add_argument("--dataset", dest="dataset", help="Dataset on which the network has been trained",
                        default="pascal")
    parser.add_argument("--confidence", dest="confidence", help="Object Confidence to filter predictions", default=0.5)
    parser.add_argument("--nms_thresh", dest="nms_thresh", help="NMS Threshhold", default=0.4)
    parser.add_argument("--cfg", dest='cfgfile', help=
    "Config file",
                        default="cfg/yolov3.cfg", type=str)
    parser.add_argument("--weights", dest='weightsfile', help=
    "weightsfile",
                        default="yolov3.weights", type=str)
    parser.add_argument("--reso", dest='reso', help=
    "Input resolution of the network. Increase to increase accuracy. Decrease to increase speed",
                        default="416", type=str)
    return parser.parse_args()


def process_pipeline(frame):
    img, orig_im, dim = prep_image(frame, inp_dim)
    im_dim = torch.FloatTensor(dim).repeat(1, 2)

    if CUDA:
        im_dim = im_dim.cuda()
        img = img.cuda()

    with torch.no_grad():
        output = model(Variable(img), CUDA)
    output = write_results(output, confidence, num_classes, nms=True, nms_conf=nms_thesh)

    if type(output) == int:
        return orig_im
    else:
        im_dim = im_dim.repeat(output.size(0), 1)
        scaling_factor = torch.min(inp_dim / im_dim, 1)[0].view(-1, 1)

        output[:, [1, 3]] -= (inp_dim - scaling_factor * im_dim[:, 0].view(-1, 1)) / 2
        output[:, [2, 4]] -= (inp_dim - scaling_factor * im_dim[:, 1].view(-1, 1)) / 2
        output[:, 1:5] /= scaling_factor

        # clip any bounding boxes that may have boundaries outside the image to the edges of our image.
        for i in range(output.shape[0]):
            output[i, [1, 3]] = torch.clamp(output[i, [1, 3]], 0.0, im_dim[i, 0])
            output[i, [2, 4]] = torch.clamp(output[i, [2, 4]], 0.0, im_dim[i, 1])

        list(map(lambda x: write(x, orig_im), output))

        return orig_im


if __name__ == '__main__':
    args = arg_parse()
    confidence = float(args.confidence)
    nms_thesh = float(args.nms_thresh)
    num_classes = 80
    CUDA = False  # torch.cuda.is_available()

    print("Loading network.....")
    model = Darknet(args.cfgfile)
    model.load_weights(args.weightsfile)
    print("Network successfully loaded")

    model.net_info["height"] = args.reso
    inp_dim = int(model.net_info["height"])
    assert inp_dim % 32 == 0
    assert inp_dim > 32

    if CUDA:
        model.cuda()

    model.eval()

    classes = load_classes('data/coco.names')
    colors = pkl.load(open("pallete", "rb"))

    mode = 'video'
    if mode == 'video':
        selector = 'out_project'
        clip = VideoFileClip('out_project.mp4').fl_image(process_pipeline)
        clip.write_videofile('out_{}_{}.mp4'.format(selector, 1), audio=False)
    else:
        test_img_dir = 'stop_sign'
        for test_img in os.listdir(test_img_dir):
            frame = cv2.imread(os.path.join(test_img_dir, test_img))

            blend = process_pipeline(frame)

            cv2.imwrite('det_stop_sign/{}'.format(test_img), blend)

            plt.imshow(cv2.cvtColor(blend, code=cv2.COLOR_BGR2RGB))
            plt.show()

