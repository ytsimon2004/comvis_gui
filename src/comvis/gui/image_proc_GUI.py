"""
Prototype
===
key:
    space: pause
     -h: command
     stop while dragging mask
     after dragging, give command for processing
        -> denoise
        -> down-sampling

    -q: rollback


feature

"""
import argparse
import logging
from pathlib import Path
from typing import final

import cv2
import numpy as np

from comvis.gui.player_GUI import CV2Player
from comvis.gui.util import COLOR_MAGENTA
from comvis.utils.proc_parameters import (
    ProcessParameters,
    load_process_parameter,
    create_default_json
)

logging.basicConfig(
    level=logging.DEBUG
)

Logger = logging.getLogger()


@final
class ImageProcPlayer(CV2Player):
    """Video Player for demonstrate the effect with cv2 image processing function"""
    @classmethod
    def cli_parser(cls) -> argparse.ArgumentParser:
        ap = super().cli_parser()

        ap.add_argument('--json', type=Path, help='json file for imaging processing func parameter')
        ap.add_argument('-O', '--output', type=Path, default=None,
                        help='output directory', dest='output')
        return ap

    def __init__(self, opt: argparse.Namespace):
        super().__init__(opt)

        # io
        if opt.output is None:
            self.output_directory = Path(opt.file).parent
        else:
            self.output_directory = Path(opt.output)

        # proc pars
        if opt.json is not None:
            self.pars: ProcessParameters = load_process_parameter(opt.json)
        else:
            json_file = self.output_directory / 'proc_pars.json'
            create_default_json(json_file)
            self.pars = load_process_parameter(json_file)

        self._output_file = self.output_directory / f'{opt.file}_proc.mp4'
        self._output_logger = self.output_directory / f'{opt.file}_proc_logger.txt'

    def start(self, pause_on_start: bool = True):
        super().start(pause_on_start)

    def handle_command(self, command: str):
        super().handle_command(command)

        match command:
            case ':gray':
                self.enqueue_message('COLOR_BGR2GRAY')
            case ':blur':
                self.enqueue_message('GaussianBlur')
            case ':sharpen':
                self.enqueue_message('filter2D')
            case ':sobelX' | ':sobelY' | ':sobelXY':
                self.enqueue_message('Sobel')
            case 'canny':
                self.enqueue_message('Canny')
            case ':r':  # rollback to original
                self.enqueue_message('rollback')

            #
            case ':h':
                self.enqueue_message(':d       :Delete the ROI')
                self.enqueue_message(':q       :Exit the GUI')
                self.enqueue_message(':gray    :Image to grayscale')
                self.enqueue_message(':blur    :Blur the image')
                self.enqueue_message(':sharpen :Sharpen the image')
                self.enqueue_message(':sobel   :Sobel Edge detection')
                self.enqueue_message(':canny   :Canny Edge detection')
                self.enqueue_message(':circle  :Circular detection' )
                self.enqueue_message(':r       :Rollback to original(raw) image')

    def proc_image(self, img: np.ndarray, command: str) -> np.ndarray:
        proc = self._get_proc_part(img)

        match command:
            case ':gray':
                proc = cv2.cvtColor(proc, cv2.COLOR_BGR2GRAY)
                proc = cv2.cvtColor(proc, cv2.COLOR_GRAY2BGR)
            case ':blur':
                pars = self.pars['GaussianBlur']
                ksize = pars['ksize']
                sigma = pars['sigma']
                proc = cv2.GaussianBlur(proc, (ksize, ksize), sigmaX=sigma, sigmaY=sigma)
            case ':sharpen':
                pars = self.pars['Filter2D']
                kernel = np.array(pars['kernel'])
                proc = cv2.filter2D(proc, -1, kernel)

            case ':sobelX' | ':sobelY' | ':sobelXY':
                k = command[1:].replace(command[1], command[1].capitalize())
                # noinspection PyTypedDict
                pars = self.pars[k]
                proc = cv2.GaussianBlur(proc, (3, 3), 0)
                proc = cv2.cvtColor(proc, cv2.COLOR_BGR2GRAY)
                proc = cv2.Sobel(proc, **pars)
                proc = cv2.cvtColor(proc, cv2.COLOR_GRAY2BGR)
            case ':canny':
                pars = self.pars['Canny']
                proc = cv2.cvtColor(proc, cv2.COLOR_BGR2GRAY)
                proc = cv2.Canny(proc, pars['lower_threshold'], pars['upper_threshold'])
                proc = cv2.cvtColor(proc, cv2.COLOR_GRAY2BGR)

            case ':circle':
                pars = self.pars['HoughCircles']
                _proc = cv2.cvtColor(proc, cv2.COLOR_BGR2GRAY)
                _proc = cv2.medianBlur(_proc, 5)
                circles = cv2.HoughCircles(_proc, minDist=_proc.shape[0] / 40, **pars)

                if circles is not None:
                    self.draw_detected_circle(proc, circles)

            case ':r':
                return img
            case _:
                return img

        if (roi := self.current_roi) is not None:
            _, x0, y0, x1, y1 = roi
            img[y0:y1, x0:x1] = proc
            return img

        return proc

    def _get_proc_part(self, img: np.ndarray) -> np.ndarray:
        """get the image part need to be processed"""
        if (roi := self.current_roi) is not None:
            _, x0, y0, x1, y1 = roi
            return img[y0:y1, x0:x1]
        else:
            return img

    @staticmethod
    def draw_detected_circle(src: np.ndarray,
                             circles: np.ndarray):
        """
        :param src: source image
        :param circles: A vector that stores sets of 3 values: xc,yc,r for each detected circle
        :return:
        """
        circles = np.uint16(np.around(circles))
        for i in circles[0, :]:
            center = (i[0], i[1])
            cv2.circle(src, center, 1, (0, 100, 100), 3)  # center
            radius = i[2]
            cv2.circle(src, center, radius, COLOR_MAGENTA, 3)  # circle outline


if __name__ == '__main__':
    parser = ImageProcPlayer.cli_parser().parse_args()
    ImageProcPlayer(parser).start()