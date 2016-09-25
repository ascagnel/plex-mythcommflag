#!/usr/bin/env python3.4

import os
import sys
import logging
import xml.etree.ElementTree as ET
import urllib.request
import platform
import re
import calendar
from datetime import datetime, timedelta
import time
import subprocess
import configparser
import argparse
from errno import EACCES

FORMAT = '%(asctime)-s %(levelname)-s %(message)s'
DATE_FORMAT = '%m-%d-%Y %H:%M:%S'
logging.basicConfig(level=logging.DEBUG,
                    format=FORMAT,
                    datefmt=DATE_FORMAT,
                    #filename = 'output.log')
                    stream=sys.stdout)
logger = logging.getLogger(__name__)

def mythcommflag_run():
    parser = argparse.ArgumentParser('mythcommflag some video files')
    parser.add_argument('source', type=str, help='Path to source.')
    args = parser.parse_args()
    print(args)

    fps_pattern = re.compile(r'(\d{2}.\d{2}) fps')
    # When calling avconv, it dumps many messages to stderr, not stdout.
    # This may break someday because of that.
    avconv_fps = subprocess.Popen(['avconv', '-i', args.source],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE).communicate()[1]
    if (fps_pattern.search(str(avconv_fps))):
        framerate = float(fps_pattern.search(str(avconv_fps)).groups()[0])
    else:
        logger.info("Could not look up FPS, trying PAL format (25FPS).")
        fps_pattern = re.compile(r'(\d{2}) fps')
        framerate = float(fps_pattern.search(str(avconv_fps)).groups()[0])

    logger.debug("Video frame rate: %s", str(framerate))

    logger.info(os.path.abspath(args.source))

    mythcommflag_command = 'mythcommflag -f \"'
    mythcommflag_command += args.source
    mythcommflag_command += '\" --outputmethod essentials'
    mythcommflag_command += ' --outputfile .mythExCommflag.edl'
    mythcommflag_command += ' --skipdb --quiet'
    mythcommflag_command += ' -v'
    logger.info("mythcommflag: [%s]", mythcommflag_command)
    os.system(mythcommflag_command)
    logger.info("mythcommflag finished")
    cutlist = open('.mythExCommflag.edl', 'r')
    cutpoints = []
    pointtypes = []
    starts_with_commercial = False
    for cutpoint in cutlist:
        if 'framenum' in cutpoint:
            line = cutpoint.split()
            logger.info("%s - {%s} -- %s - {%s}",
                        line[0], line[1],
                        line[2], line[3])
            if line[1] is '0' and line[3] is '4':
                starts_with_commercial = True
            cutpoints.append(line[1])
            pointtypes.append(line[3])
    cutlist.close()
    os.system('rm .mythExCommflag.edl')
    logger.debug("Starts with commercial? %s",  str(starts_with_commercial))
    logger.debug("Found %s cut points", str(len(cutpoints)))
    segments = 0
    for cutpoint in cutpoints:
        index = cutpoints.index(cutpoint)
        startpoint = float(cutpoints[index])/framerate
        duration = 0
        if index is 0 and not starts_with_commercial:
            logger.debug("Starting with non-commercial")
            duration = float(cutpoints[0])/framerate
            startpoint = 0
        elif pointtypes[index] is '4':
            logger.debug("Skipping cut point type 4")
            continue
        elif (index+1) < len(cutpoints):
            duration = (float(cutpoints[index+1]) -
                        float(cutpoints[index]))/framerate
        logger.debug("Start point [%s]", str(startpoint))
        logger.debug("Duration of segment %s: %s",
                     str(segments),
                     str(duration))
        if duration is 0:
            avconv_command = ('avconv -v 16 -i \"' + args.source + '\" -ss ' +
                              str(startpoint) + ' -c copy output' +
                              str(segments) + '.mpg')
        else:
            avconv_command = ('avconv -v 16 -i \"' + args.source + '\" -ss ' +
                              str(startpoint) + ' -t ' + str(duration) +
                              ' -c copy output' + str(segments) + '.mpg')
        logger.info("Running avconv command line {%s}", avconv_command)
        os.system(avconv_command)
        segments = segments + 1
    current_segment = 0
    concat_command = 'cat'
    while current_segment < segments:
        concat_command += ' output' + str(current_segment) + '.mpg'
        current_segment = current_segment + 1
    concat_command += ' >> \"'
    concat_command += args.source
    concat_command += '\"'
    logger.info("Merging files with command %s", concat_command)
    os.system(concat_command)
    os.system('rm output*.mpg')
    os.system('rm tempfile.mpg')
    return 

if __name__ == "__main__":
    mythcommflag_run()
    
