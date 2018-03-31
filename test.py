from __future__ import print_function, division

import os
os.environ['MXNET_CUDNN_AUTOTUNE_DEFAULT']='0'
import time
import shutil
import logging
import argparse
import cv2
import mxnet as mx
from mxnet import nd, autograd as ag, gluon as gl
from mxnet.gluon import nn
import numpy as np
import pandas as pd
from tensorboardX import SummaryWriter
from dataset import FashionAIKPSDataSet, process_cv_img
from model import PoseNet
from config import cfg


def draw(img, ht):
    h, w = img.shape[:2]
    ht = cv2.resize(ht, (w, h))
    ht = (ht * 255).astype(np.uint8)
    ht = cv2.applyColorMap(ht, cv2.COLORMAP_JET)
    drawed = cv2.addWeighted(img, 0.5, ht, 0.5, 0)
    return drawed


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', type=int, default='-1')
    parser.add_argument('--epoch', type=int, default=0)
    parser.add_argument('--data-dir', type=str, default='./data')
    parser.add_argument('--category', type=str, default='skirt', choices=['blouse', 'skirt', 'outwear', 'dress', 'trousers'])
    parser.add_argument('--cpm-stages', type=int, default=5)
    parser.add_argument('--cpm-channels', type=int, default=64)
    parser.add_argument('--optim', type=str, default='sgd', choices=['sgd', 'adam'])
    parser.add_argument('--backbone', type=str, default='vgg19', choices=['vgg19'])
    args = parser.parse_args()
    print(args)
    # hyper parameters
    ctx = mx.cpu(0) if args.gpu == -1 else mx.gpu(args.gpu)
    cpm_stages = args.cpm_stages
    cpm_channels = args.cpm_channels
    epoch = args.epoch
    optim = args.optim
    category = args.category
    data_dir = args.data_dir
    backbone = args.backbone
    base_name = '%s-%s-S%d-C%d-%s' % (category, backbone, cpm_stages, cpm_channels, optim)
    # model
    num_kps = len(cfg.LANDMARK_IDX[category])
    num_limb = len(cfg.PAF_LANDMARK_PAIR[category])
    net = PoseNet(num_kps=num_kps, num_limb=num_limb, stages=cpm_stages, channels=cpm_channels)
    creator, featname, fixed = cfg.BACKBONE[backbone]
    net.init_backbone(creator, featname, fixed)
    net.load_params('./output/%s-%04d.params' % (base_name, epoch), mx.cpu(0))
    net.collect_params().reset_ctx(ctx)
    # data
    df = pd.read_csv(os.path.join(data_dir, 'test/test.csv'))
    num = len(df)
    for idx, row in df.iterrows():
        if row['image_category'] == category:
            path = os.path.join(data_dir, 'test', row['image_id'])
            img = cv2.imread(path)
            if img is None:
                print(path)
                continue
            data = process_cv_img(img)
            batch = mx.nd.array(data[np.newaxis], ctx)
            out = net(batch)
            heatmap = out[-1][0][0].asnumpy()
            paf = out[-1][1][0].asnumpy()
            heatmap = heatmap[::-1].max(axis=0)
            n, h, w = paf.shape
            paf = paf.reshape((n // 2, 2, h, w))
            paf = np.sqrt(np.square(paf[:, 0]) + np.square(paf[:, 1]))
            paf = paf.max(axis=0)

            dr1 = draw(img, heatmap)
            dr2 = draw(img, paf)
            cv2.imshow('heatmap', dr1)
            cv2.imshow('paf', dr2)
            key = cv2.waitKey(0)
            if key == 27:
                break

