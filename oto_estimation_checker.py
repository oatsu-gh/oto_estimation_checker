#!/usr/bin/env python3
# Copyright (c) 2020 oatsu
"""
moresampler や setParam の原音設定機能で1拍以上ずれている部分を検出するツール
"""

from operator import attrgetter
from os.path import exists, isdir
# from pprint import pprint
from statistics import median
from sys import argv
from typing import List

import utaupy
# from tqdm import tqdm
from utaupy.otoini import Oto, OtoIni


def remove_cv_and_rest(otoini):
    """
    OtoIniから単独音と休符や息音素を除去する。
    """
    otoini.data = [
        oto for oto in otoini if all([
            ' ' in oto.alias,
            ' R' not in oto.alias,
            ' -' not in oto.alias,
            '息' not in oto.alias,
            ' を' not in oto.alias
        ])
    ]


def sorted_otoini(otoini: OtoIni):
    """
    OtoIniを wavファイル名昇順、左ブランク昇順の優先度でソート
    """
    sorted_otoini_obj = sorted(otoini, key=attrgetter('filename', 'offset'))
    return sorted_otoini_obj


def median_of_first_preutterance(list_oto_2d: list) -> float:
    """
    wavファイル中で最初のエイリアスの先行発声位置を
    全ファイルについて調査し、その中央値を返す。
    """
    median_start = median([
        (l_oto[0].offset + l_oto[0].preutterance) for l_oto in list_oto_2d
    ])
    return median_start


def median_of_ms_per_beat(list_oto_2d: list) -> float:
    """
    otoiniはwavファイル名順にソートしておく。
    先行発声間の時間を計算し、中央値を返す。
    1拍当たりの時間の基準値になる。
    """
    # 先行発声間の時間をリストにする。
    l_times = []
    # 各wavファイルについて処理
    for l_oto in list_oto_2d:
        # 各エイリアスについて処理
        for i, oto in enumerate(l_oto[1:], 1):
            current_start_time = oto.offset + oto.preutterance
            previous_start_time = l_oto[i - 1].offset + l_oto[i - 1].preutterance
            duration = current_start_time - previous_start_time
            if duration != 0:
                l_times.append(duration)
    return median(l_times)


def otoini_2d(otoini: OtoIni) -> list:
    """
    OtoIniを分割して、wavファイル名ごとに区切った二次元リストにする。
    [[Oto, Oto, ..., Oto], [Oto, Oto, ...], ...]
    """
    l_2d = []
    filename = ''
    for oto in otoini:
        if filename != oto.filename:
            filename = oto.filename
            l: List[Oto] = []
            l_2d.append(l)
        l.append(oto)
    return l_2d


def detect_bad_wavfiles(list_oto_2d, ms_per_beat, median_start, threshold: float = 0.5):
    """
    各ファイルの最初のエイリアスをチェックする。
    明らかにずれてる原音の音声ファイル名をリストにする。
    """
    t_floor = median_start - ms_per_beat * threshold
    t_ceil = median_start + ms_per_beat * threshold

    # チェックに通過できなかったファイル名のリスト
    bad_start_filenames: List[str] = []
    # 基準時刻とどの程度ずれてるかチェック
    for l_oto in list_oto_2d:
        first_oto = l_oto[0]
        if not t_floor < (first_oto.offset + first_oto.preutterance) < t_ceil:
            bad_start_filenames.append(str(first_oto.filename))
    return bad_start_filenames


def detect_bad_aliases(list_oto_2d, ms_per_beat, threshold: float = 0.5) -> list:
    """
    全エイリアスの長さをチェックする。
    明らかに場所がおかしい原音のリストを返す。
    """
    bad_alias_wavfiles: List[str] = []

    for l_oto in list_oto_2d:
        for i, oto in enumerate(l_oto[1:], 1):
            # 下限時刻と上限時刻を設定
            t_floor = ms_per_beat * (1 - threshold)
            t_ceil = ms_per_beat * (1 + threshold)

            # 前のエイリアスの先行発声からどのくらい離れているか調べる
            current_start_time = oto.offset + oto.preutterance
            previous_start_time = l_oto[i - 1].offset + l_oto[i - 1].preutterance
            relative_position = current_start_time - previous_start_time
            # 「お」「を」などの複製エイリアスでは0になって検出されるので回避
            if relative_position == 0:
                continue

            # print(int(t_floor), int(relative_position), int(t_ceil), oto.alias)
            # 下限から上限までに収まらなければダメなリストに入れる
            if not t_floor < relative_position < t_ceil:
                # print(int(t_floor), int(relative_position), int(t_ceil), oto.alias, oto.filename)
                # print('------------warn↑-----------------------------')
                bad_alias_wavfiles.append(str(oto.filename))
                break
    return bad_alias_wavfiles


def main(path):
    """
    oto.iniを読んで処理する。
    """
    path = path.strip('"')
    # 原音設定ファイルではなくフォルダが指定された時
    if isdir(path):
        path_otoini = f'{path}/oto.ini'
        assert exists(path_otoini), '指定されたフォルダにoto.iniファイルがありません。'
    else:
        path_otoini = path

    # ファイル出力用の文字列
    s = ''

    otoini = utaupy.otoini.load(path_otoini)
    otoini.data = sorted_otoini(otoini)
    otoini.write('sorted_otoini.txt')
    s += f'全エイリアス数: {len(otoini)}\n'

    remove_cv_and_rest(otoini)
    s += f'連続音かつ非語尾エイリアス数: {len(otoini)}\n'

    l_2d = otoini_2d(otoini)
    s += f'音声ファイル数: {len(l_2d)}\n'

    # 最初のエイリアスの先行発声+左ブランクの時刻の中央値
    median_start = median_of_first_preutterance(l_2d)
    s += f'最初のエイリアスの発声時刻の中央値 (ms): {int(median_start)}\n'

    # 1拍当たりの時間の中央値
    ms_per_beat = median_of_ms_per_beat(l_2d)

    s += f'1拍当たりの時間の中央値 (ms): {int(ms_per_beat)}\n'
    s += f'median of time per beat (ms): {int(ms_per_beat)}\n'
    s += '\n\n'

    s += '原音設定ミスの疑いがあるwavファイル名(明らかにずれてる)------------------\n'
    s += '1拍めがずれてそう------------------\n'
    s += '\n'.join(detect_bad_wavfiles(l_2d, ms_per_beat, median_start, threshold=0.9)) + '\n'
    s += '2拍め以降がずれてそう--------------\n'
    s += '\n'.join(detect_bad_aliases(l_2d, ms_per_beat, threshold=0.9)) + '\n\n'

    s += '原音設定ミスの疑いがあるwavファイル名(緩く検出)------------------\n'
    s += '1拍めがずれてそう------------------\n'
    s += '\n'.join(detect_bad_wavfiles(l_2d, ms_per_beat, median_start, threshold=0.3)) + '\n'
    s += '2拍め以降がずれてそう--------------\n'
    s += '\n'.join(detect_bad_aliases(l_2d, ms_per_beat, threshold=0.3)) + '\n\n'

    s += '原音設定ミスの疑いがあるwavファイル名(そこそこ検出)------------------\n'
    s += '1拍めがずれてそう------------------\n'
    s += '\n'.join(detect_bad_wavfiles(l_2d, ms_per_beat, median_start, threshold=0.25)) + '\n'
    s += '2拍め以降がずれてそう--------------\n'
    s += '\n'.join(detect_bad_aliases(l_2d, ms_per_beat, threshold=0.25)) + '\n\n'

    s += '原音設定ミスの疑いがあるwavファイル名(厳しめに検出)------------------\n'
    s += '1拍めがずれてそう------------------\n'
    s += '\n'.join(detect_bad_wavfiles(l_2d, ms_per_beat, median_start, threshold=0.2)) + '\n'
    s += '2拍め以降がずれてそう--------------\n'
    s += '\n'.join(detect_bad_aliases(l_2d, ms_per_beat, threshold=0.2)) + '\n\n'

    with open('result.txt', 'w', encoding='utf-8') as f:
        f.write(s)


if __name__ == '__main__':
    print('_____ξ・ヮ・) < 自動原音設定でずれてる部分を検出するツール v0.0.1 ________')
    print('Copyright (c) 2001-2020 Python Software Foundation')
    print('Copyright (c) 2020 oatsu')
    if len(argv) > 1:
        main(argv[1])
    else:
        main(input('原音設定ファイルをD&Dしてください / Select oto.ini file\n>>> '))
    input('Press Enter to exit.')
