#!/usr/bin/env python3

import argparse
import os
import warnings

import numpy as np

import colorization.config as config
from colorization.util.argparse import nice_help_formatter
from colorization.util.image import \
    imread, imsave, lab_to_rgb, numpy_to_torch, resize, rgb_to_lab, torch_to_numpy


USAGE = \
"""run_evaluation.py [-h|--help]
                         --config CONFIG
                         [--input-image IMAGE]
                         [--input-dir IMAGE_DIR]
                         [--output-image IMAGE]
                         [--output-dir IMAGE_DIR]
                         [--input-size SIZE]
                         [--pretrain-proto PROTOTXT]
                         [--pretrain-model CAFFEMODEL]
                         [--checkpoint CHECKPOINT]
                         [--checkpoint-dir DIR]
                         [--verbose]"""


def _err(msg):
    raise ValueError(msg)


def _predict_image(input_image, input_size, output_image):
    # load input image
    img_rgb = imread(input_image)
    img_rgb_resized = resize(img_rgb, (input_size,) * 2)

    h_orig, w_orig, _ = img_rgb.shape

    # convert colorspace
    img_lab = rgb_to_lab(img_rgb)
    img_lab_resized = rgb_to_lab(img_rgb_resized)

    # run prediction
    l_batch = numpy_to_torch(img_lab_resized[:, :, :1])
    ab_pred = torch_to_numpy(model.predict(l_batch))

    # assemble and save
    img_lab_pred = np.dstack(
        (img_lab[:, :, :1], resize(ab_pred, (h_orig, w_orig))))

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')

        imsave(output_image, lab_to_rgb(img_lab_pred))


if __name__ == '__main__':
    # parse command line arguments
    def fmt(prog):
        return argparse.HelpFormatter(prog, max_help_position=40)

    parser = argparse.ArgumentParser(formatter_class=nice_help_formatter(),
                                     usage=USAGE)

    parser.add_argument('--config',
                        required=True,
                        help="training configuration JSON file")

    parser.add_argument('--input-image',
                        metavar='IMAGE',
                        help="path to single input image")

    parser.add_argument('--input-dir',
                        metavar='IMAGE_DIR',
                        help="path to directory containing input images")

    parser.add_argument('--output-image',
                        metavar='IMAGE',
                        help=str("location to which predicted color image is "
                                 "to be written"))

    parser.add_argument('--output-dir',
                        metavar='IMAGE_DIR',
                        help="path to directory in which to write output images")

    parser.add_argument('--input-size',
                        metavar='SIZE',
                        default=224,
                        help=str("size (both height and width) to which image "
                                 "is rescaled before putting to it through the "
                                 "network (default is %(default)d)"))

    parser.add_argument('--pretrain-proto',
                        metavar='PROTOTXT',
                        help="Caffe prototxt file")

    parser.add_argument('--pretrain-model',
                        metavar='CAFFEMODEL',
                        help="Caffe caffemodel file")

    parser.add_argument('--checkpoint',
                        metavar='CHECKPOINT',
                        help=str("specific model checkpoint file from which to "
                                 "load model for prediction"))

    parser.add_argument('--checkpoint-dir',
                        metavar='DIR',
                        help=str("model checkpoint directory, if this is given "
                                 "and --model-checkpoint is not, the model "
                                 "corresponding to the most recent checkpoint "
                                 "is used to perform prediction"))

    parser.add_argument('--verbose',
                        action='store_true',
                        help="display progress")

    args = parser.parse_args()

    # validate arguments
    if (args.input_image is None) == (args.input_dir is None):
        _err("either --input-image OR --input-dir must be specified")

    if (args.input_image is not None) and (args.output_image is None):
        _err("--input-image and --output-image must be specified together")
    elif (args.input_dir is not None) and (args.output_dir is None):
        _err("--input-dir and --output-dir must be specified together")

    if (args.pretrain_proto is None) != (args.pretrain_model is None):
        _err("--pretrain-proto and --pretrain-model must be specified together")

    if (args.checkpoint is not None) and (args.checkoint_dir is not None):
        _err("--checkpoint and --checkpoint-dir may not be specified together")

    pretrained = args.pretrain_proto is not None

    checkpointed = (args.checkpoint is not None) or \
                   (args.checkpoint_dir is not None)

    if pretrained == checkpointed:
        _err("either pretrained network OR checkpoint must be specified")

    # load configuration file(s)
    cfg = config.get_config(args.config)
    cfg = config.parse_config(cfg)

    model = cfg['model']

    # load pretrained weights
    if pretrained:
        model.network.init_from_caffe(args.pretrain_proto, args.pretrain_model)

    # load from checkpoint
    if checkpointed:
        if args.checkpoint is not None:
            checkpoint_path = args.checkpoint
        elif args.checkpoint_dir is not None:
            checkpoint_path, _ = model.find_latest_checkpoint(args.checkpoint_dir)

        model.load(checkpoint_path)

    # predicted image(s)
    if args.input_image is not None:
        _predict_image(args.input_image, args.input_size, args.output_image)
    elif args.input_dir is not None:
        if not os.path.exists(args.output_dir):
            os.mkdir(args.output_dir)

        for image in os.listdir(args.input_dir):
            if args.verbose:
                print("processing '{}'".format(image))

            in_image = os.path.join(args.input_dir, image)
            out_image = os.path.join(args.output_dir, image)

            _predict_image(in_image, args.input_size, out_image)
