#!/usr/bin/env python2

import argparse
from PIL import Image
from onnx import onnx
import sys
import struct

def main():
    parser = argparse.ArgumentParser(description='convert ONNX tensor to JPEG image.')
    parser.add_argument('input', type=str, metavar='INPUT.pb', 
                        help='ONNX tensor protocol buffer file')
    parser.add_argument('--output', '-o', type=str, metavar='OUTPUT.jpg', default='output.jpg',
                        help='Output JPEG file (default: output.jpg)')
    args = parser.parse_args()

    # read input tensor
    input_tensor = onnx.TensorProto()
    with open(args.input, 'rb') as f:
        input_tensor.ParseFromString(f.read())

    # input tensor dimension should be in form [1, 3, *, *]
    sys.stdout.write('# of dims: {}\n'.format(len(input_tensor.dims)))
    sys.stdout.write('dims: {}\n'.format(input_tensor.dims))

    assert input_tensor.data_type == 1
    assert len(input_tensor.dims) == 4
    assert input_tensor.dims[0] == 1 and input_tensor.dims[1] == 3

    # create output image for writing
    width_dim, height_dim = 2, 3
    image_width, image_height = input_tensor.dims[width_dim], input_tensor.dims[height_dim]
    pixel_count = image_width * image_height
    output_image = Image.new('RGB', (image_width, image_height), 'black')
    output_pixels = output_image.load()

    # get the # of values in tensor
    size = 1
    for dim in input_tensor.dims:
        size *= dim

    input_tensor_array = struct.unpack('%sf' % size, input_tensor.raw_data)
    offset = 0
    for row in range(input_tensor.dims[width_dim]):
        for col in range(input_tensor.dims[height_dim]):
            r = int(input_tensor_array[offset])
            g = int(input_tensor_array[offset + pixel_count])
            b = int(input_tensor_array[offset + 2 * pixel_count])
            output_pixels[row, col] = (r, g, b)

            offset = offset + 1

    output_image.save(args.output, 'JPEG')
    return 0

if __name__ == '__main__':
    sys.exit(main())
