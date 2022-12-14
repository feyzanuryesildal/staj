r"""Convert raw COCO dataset to TFRecord for object_detection.
Please note that this tool creates sharded output files.
Example usage:
    python create_coco_tf_record.py --logtostderr \
      --train_image_dir="${TRAIN_IMAGE_DIR}" \
      --val_image_dir="${VAL_IMAGE_DIR}" \
      --test_image_dir="${TEST_IMAGE_DIR}" \
      --train_annotations_file="${TRAIN_ANNOTATIONS_FILE}" \
      --val_annotations_file="${VAL_ANNOTATIONS_FILE}" \
      --testdev_annotations_file="${TESTDEV_ANNOTATIONS_FILE}" \
      --output_dir="${OUTPUT_DIR}"
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from absl import app
import hashlib
import io
import json
import os
import contextlib2
import numpy as np
import PIL.Image

from pycocotools import mask
import tensorflow as tf
from tqdm import tqdm
#import tensorflow._api.v2.compat.v1 as tf

flags = tf.app.flags
tf.flags.DEFINE_boolean('mini', False,
                        'Create coco trainval35k or not')
tf.flags.DEFINE_boolean('include_masks', True,
                        'Whether to include instance segmentations masks '
                        '(PNG encoded) in the result. default: False.')
tf.flags.DEFINE_string('train_image_dir', '',
                       'Training image directory.')
tf.flags.DEFINE_string('val_image_dir', '',
                       'Validation image directory.')
tf.flags.DEFINE_string('test_image_dir', '',
                       'Test image directory.')
tf.flags.DEFINE_string('train_annotations_file', '',
                       'Training annotations JSON file.')
tf.flags.DEFINE_string('val_annotations_file', '',
                       'Validation annotations JSON file.')
tf.flags.DEFINE_string('testdev_annotations_file', '',
                       'Test-dev annotations JSON file.')
tf.flags.DEFINE_string('output_dir', './tmp/', 'Output data directory.')

FLAGS = flags.FLAGS

tf.logging.set_verbosity(tf.logging.INFO)


def open_sharded_output_tfrecords(exit_stack, base_path, num_shards):
    """Opens all TFRecord shards for writing and adds them to an exit stack.
    Args:
      exit_stack: A context2.ExitStack used to automatically closed the TFRecords
        opened in this function.
      base_path: The base path for all shards
      num_shards: The number of shards
    Returns:
      The list of opened TFRecords. Position k in the list corresponds to shard k.
    """
    tf_record_output_filenames = [
        '{}-{:05d}-of-{:05d}'.format(base_path, idx + 1, num_shards)
        for idx in range(num_shards)
    ]

    tfrecords = [
        exit_stack.enter_context(tf.python_io.TFRecordWriter(file_name))
        for file_name in tf_record_output_filenames
    ]

    return tfrecords


def create_category_index(categories):
    """Creates dictionary of COCO compatible categories keyed by category id.
    Args:
      categories: a list of dicts, each of which has the following keys:
        'id': (required) an integer id uniquely identifying this category.
        'name': (required) string representing category name
          e.g., 'cat', 'dog', 'pizza'.
    Returns:
      category_index: a dict containing the same entries as categories, but keyed
        by the 'id' field of each category.
    """
    category_index = {}
    for cat in categories:
        category_index[cat['id']] = cat
    return category_index


def create_tf_example(image,
                      annotations_list,
                      image_dir,
                      category_index,
                      include_masks=False):
    """Converts image and annotations to a tf.Example proto.
    Args:
      image: dict with keys:
        [u'license', u'file_name', u'coco_url', u'height', u'width',
        u'date_captured', u'flickr_url', u'id']
      annotations_list:
        list of dicts with keys:
        [u'segmentation', u'area', u'iscrowd', u'image_id',
        u'bbox', u'category_id', u'id']
        Notice that bounding box coordinates in the official COCO dataset are
        given as [x, y, width, height] tuples using absolute coordinates where
        x, y represent the top-left (0-indexed) corner.  This function converts
        to the format expected by the Tensorflow Object Detection API (which is
        which is [ymin, xmin, ymax, xmax] with coordinates normalized relative
        to image size).
      image_dir: directory containing the image files.
      category_index: a dict containing COCO category information keyed
        by the 'id' field of each category.  See the
        label_map_util.create_category_index function.
      include_masks: Whether to include instance segmentations masks
        (PNG encoded) in the result. default: False.
    Returns:
      example: The converted tf.Example
      num_annotations_skipped: Number of (invalid) annotations that were ignored.
    Raises:
      ValueError: if the image pointed to by data['filename'] is not a valid JPEG
    """
    image_height = image['height']
    image_width = image['width']
    filename = image['file_name']
    image_id = image['id']

    full_path = os.path.join(image_dir, filename)
    with tf.gfile.GFile(full_path, 'rb') as fid:
        encoded_jpg = fid.read()
    key = hashlib.sha256(encoded_jpg).hexdigest()

    xmin = []
    xmax = []
    ymin = []
    ymax = []
    is_crowd = []
    category_names = []
    category_ids = []
    area = []
    encoded_mask_png = []
    num_annotations_skipped = 0
    for object_annotations in annotations_list:
        (x, y, width, height) = tuple(object_annotations['bbox'])
        if width <= 0 or height <= 0:
            num_annotations_skipped += 1
            continue
        if x + width > image_width or y + height > image_height:
            num_annotations_skipped += 1
            continue
        xmin.append(float(x) / image_width)
        xmax.append(float(x + width) / image_width)
        ymin.append(float(y) / image_height)
        ymax.append(float(y + height) / image_height)
        is_crowd.append(object_annotations['iscrowd'])
        category_id = int(object_annotations['category_id'])
        category_ids.append(category_id)
        category_names.append(category_index[category_id]['name'].encode('utf8'))
        area.append(object_annotations['area'])

        if include_masks:
            run_len_encoding = mask.frPyObjects(object_annotations['segmentation'],
                                                image_height, image_width)
            binary_mask = mask.decode(run_len_encoding)
            if not object_annotations['iscrowd']:
                binary_mask = np.amax(binary_mask, axis=2)
            pil_image = PIL.Image.fromarray(binary_mask)
            output_io = io.BytesIO()
            pil_image.save(output_io, format='PNG')
            encoded_mask_png.append(output_io.getvalue())
    feature_dict = {
        'image/height':
            int64_feature(image_height),
        'image/width':
            int64_feature(image_width),
        'image/filename':
            bytes_feature(filename.encode('utf8')),
        'image/source_id':
            bytes_feature(str(image_id).encode('utf8')),
        'image/key/sha256':
            bytes_feature(key.encode('utf8')),
        'image/encoded':
            bytes_feature(encoded_jpg),
        'image/format':
            bytes_feature('jpeg'.encode('utf8')),
        'image/object/bbox/xmin':
            float_list_feature(xmin),
        'image/object/bbox/xmax':
            float_list_feature(xmax),
        'image/object/bbox/ymin':
            float_list_feature(ymin),
        'image/object/bbox/ymax':
            float_list_feature(ymax),
        'image/object/class/text':
            bytes_list_feature(category_names),
        'image/object/is_crowd':
            int64_list_feature(is_crowd),
        'image/object/area':
            float_list_feature(area),
    }
    if include_masks:
        feature_dict['image/object/mask'] = (
            bytes_list_feature(encoded_mask_png))
    example = tf.train.Example(features=tf.train.Features(feature=feature_dict))
    return key, example, num_annotations_skipped


def _create_tf_record_from_coco_annotations(
        annotations_file, image_dir, output_path, include_masks, num_shards):
    """Loads COCO annotation json files and converts to tf.Record format.
    Args:
      annotations_file: JSON file containing bounding box annotations.
      image_dir: Directory containing the image files.
      output_path: Path to output tf.Record file.
      include_masks: Whether to include instance segmentations masks
        (PNG encoded) in the result. default: False.
      num_shards: number of output file shards.
    """
    with contextlib2.ExitStack() as tf_record_close_stack, tf.gfile.GFile(annotations_file, 'r') as fid:
        output_tfrecords = open_sharded_output_tfrecords(tf_record_close_stack, output_path, num_shards)
        groundtruth_data = json.load(fid)
        images = groundtruth_data['images']
        category_index = create_category_index(groundtruth_data['categories'])

        annotations_index = {}
        if 'annotations' in groundtruth_data:
            tf.logging.info('Found groundtruth annotations. Building annotations index.')
            for annotation in groundtruth_data['annotations']:
                image_id = annotation['image_id']
                if image_id not in annotations_index:
                    annotations_index[image_id] = []
                annotations_index[image_id].append(annotation)
        missing_annotation_count = 0
        for image in images:
            image_id = image['id']
            if image_id not in annotations_index:
                missing_annotation_count += 1
                annotations_index[image_id] = []
        tf.logging.info('%d images are missing annotations.', missing_annotation_count)

        total_num_annotations_skipped = 0
        idx = 0
        for image in tqdm(images):
            annotations_list = annotations_index[image['id']]
            _, tf_example, num_annotations_skipped = create_tf_example(image, annotations_list, image_dir,
                                                                       category_index, include_masks)
            total_num_annotations_skipped += num_annotations_skipped
            shard_idx = idx % num_shards
            output_tfrecords[shard_idx].write(tf_example.SerializeToString())
            idx += 1
        tf.logging.info('Finished writing, skipped %d annotations.', total_num_annotations_skipped)


def main(_):
    if FLAGS.mini:
        create_coco_trainval35k()
        quit()
    assert FLAGS.train_image_dir, '`train_image_dir` missing.'
    assert FLAGS.val_image_dir, '`val_image_dir` missing.'
    assert FLAGS.test_image_dir, '`test_image_dir` missing.'
    assert FLAGS.train_annotations_file, '`train_annotations_file` missing.'
    assert FLAGS.val_annotations_file, '`val_annotations_file` missing.'
    assert FLAGS.testdev_annotations_file, '`testdev_annotations_file` missing.'

    if not tf.gfile.IsDirectory(FLAGS.output_dir):
        tf.gfile.MakeDirs(FLAGS.output_dir)
    train_output_path = os.path.join(FLAGS.output_dir, 'coco_2014_train.tfrecord')
    val_output_path = os.path.join(FLAGS.output_dir, 'coco_2014_val.tfrecord')
    testdev_output_path = os.path.join(FLAGS.output_dir, 'coco_2014_testdev.tfrecord')

    print('Include mask: {}'.format(FLAGS.include_masks))
    _create_tf_record_from_coco_annotations(
        FLAGS.train_annotations_file,
        FLAGS.train_image_dir,
        train_output_path,
        FLAGS.include_masks,
        num_shards=10)
    _create_tf_record_from_coco_annotations(
        FLAGS.val_annotations_file,
        FLAGS.val_image_dir,
        val_output_path,
        FLAGS.include_masks,
        num_shards=5)
    _create_tf_record_from_coco_annotations(
        FLAGS.testdev_annotations_file,
        FLAGS.test_image_dir,
        testdev_output_path,
        FLAGS.include_masks,
        num_shards=5)


def create_coco_trainval35k():
    assert FLAGS.val_image_dir, '`val_image_dir` missing.'
    assert FLAGS.train_annotations_file, '`train_annotations_file` missing.'
    assert FLAGS.val_annotations_file, '`val_annotations_file` missing.'

    if not tf.gfile.IsDirectory(FLAGS.output_dir):
        tf.gfile.MakeDirs(FLAGS.output_dir)
    train_output_path = os.path.join(FLAGS.output_dir, 'coco_2014_valminusminival.tfrecord')  # coco_trainval35k
    val_output_path = os.path.join(FLAGS.output_dir, 'coco_2014_minival.tfrecord')

    print('Include mask: {}'.format(FLAGS.include_masks))
    _create_tf_record_from_coco_annotations(
        FLAGS.train_annotations_file,
        FLAGS.val_image_dir,
        train_output_path,
        FLAGS.include_masks,
        num_shards=5)
    _create_tf_record_from_coco_annotations(
        FLAGS.val_annotations_file,
        FLAGS.val_image_dir,
        val_output_path,
        FLAGS.include_masks,
        num_shards=1)
import tensorflow as tf


def int64_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))


def int64_list_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int64List(value=value))


def bytes_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))


def bytes_list_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=value))


def float_list_feature(value):
    return tf.train.Feature(float_list=tf.train.FloatList(value=value))


def read_examples_list(path):
    """Read list of training or validation examples.
    The file is assumed to contain a single example per line where the first
    token in the line is an identifier that allows us to find the image and
    annotation xml for that example.
    For example, the line:
    xyz 3
    would allow us to find files xyz.jpg and xyz.xml (the 3 would be ignored).
    Args:
      path: absolute path to examples list file.
    Returns:
      list of example identifiers (strings).
    """
    with tf.gfile.GFile(path) as fid:
        lines = fid.readlines()
    return [line.strip().split(' ')[0] for line in lines]


def recursive_parse_xml_to_dict(xml):
    """Recursively parses XML contents to python dict.
    We assume that `object` tags are the only ones that can appear
    multiple times at the same level of a tree.
    Args:
      xml: xml tree obtained by parsing XML file contents using lxml.etree
    Returns:
      Python dictionary holding XML contents.
    """
    if len(xml) == 0:
        return {xml.tag: xml.text}
    result = {}
    for child in xml:
        child_result = recursive_parse_xml_to_dict(child)
        if child.tag != 'object':
            result[child.tag] = child_result[child.tag]
        else:
            if child.tag not in result:
                result[child.tag] = []
            result[child.tag].append(child_result[child.tag])
    return {xml.tag: result}


if __name__ == '__main__':
    app.run(main)