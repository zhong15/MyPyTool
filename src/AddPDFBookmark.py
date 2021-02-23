import os
import logging
import logging.config

from PyPDF2 import PdfFileWriter, PdfFileReader

logging.config.fileConfig("resources/logger.config")

LOG = logging.getLogger('log02')


class BookmarkParser:
    """书签解析器

    第一行格式：留空行或一个整数，表示实际页码的基数
    书签格式：{layer}{title}{first space}{page no}
    {layer}: 由 0 个或 4 的倍数的空格，每 4 个空格表示一个级别
    {title}: 标题，至少一个字符
    {first space}: 第一个位置分隔符，至少 1 个空格
    {page no}: 页码，必须是正整数
    """

    def __init__(self, path):
        """初始化书签解析器

        Args:
            path: 书签路径
        Returns:
            书签解析器对象
        """
        if path is None or len(path) == 0:
            raise RuntimeError('书签路径为空')
        self.__path = path

    def parse(self):
        """解析书签

        Returns:
            3 个元素组成的元组列表：（级别，标题，页码）
        """
        LOG.info('开始解析书签')
        bm_list = self.__read_bookmark_as_list()
        if bm_list is None or len(bm_list) == 0:
            LOG.warn('书签内容为空'.format(self.__path))
            return None

        bml = []
        self.__line_no = 0
        for bm in bm_list:
            self.__line_no += 1
            bm = BookmarkParser.__remove_end_line_char(bm)
            # match page no base
            if self.__line_no == 1:
                self.__page_no_base = self.__parse_page_no_base(bm)
                continue
            # parse bookmark
            if bm is None or len(bm) == 0:
                continue
            bml.append(self.__parse_bookmark(bm))

        bml = BookmarkParser.__add_id_parent_id(bml)
        bml = BookmarkParser.__add_serial_no_to_title(bml)
        return bml

    def __read_bookmark_as_list(self):
        """读取书签为字符串列表

        Returns:
            书签字符串列表
        """
        LOG.debug('开始读取书签文件')
        bm_list = []
        with open(self.__path) as bm:
            for i in bm:
                bm_list.append(i)
        return bm_list

    @staticmethod
    def __remove_end_line_char(str):
        """删除末尾的换行字符

        Args:
            str: 字符串
        Returns:
            None 或末尾不带换行字符的字符串
        """
        if str is None or len(str) == 0:
            return None
        if str[len(str) - 1] == '\n':
            return str[0:len(str) - 1]
        return str

    def __parse_page_no_base(self, str):
        """解析第一行实际页码的递增基数

        留空行或一个整数
        """
        LOG.debug('开始解析实际页码的递增基数')
        if str is None or len(str) == 0:
            return 0

        for c in str:
            if c < '0' or c > '9':
                self._raise_message('page no 不是数字')

        return int(str)

    def __parse_bookmark(self, str):
        """解析书签

        Args:
            str: 书签字符串
        Returns:
            3 个元素的元组：（级别，标题，页码）
        """
        # bookmark = {layer}{title}{first space}{page no}
        if str is None or len(str) == 0:
            LOG.warn('跳过解析空行')
            return

        i = 0
        (i, layer) = self.__match_layer(str, i)
        (i, title) = self.__match_title(str, i)
        (i, _) = self.__match_first_space(str, i)
        (i, page_no) = self.__match_page_no(str, i)

        return (layer, title, page_no)

    def __match_layer(self, str, s):
        """匹配级别

        Args:
            str: 书签字符串
            s: 开始位置
        Returns:
            2 个元素的元组：(下一个位置，级别)
        """
        self.__check_str_index(str, s)

        if str[s] != ' ':
            return (s, 0)

        e = BookmarkParser.__space_end_index(str, s)
        self.__check_str_index(str, e)

        space_len = e - s + 1
        if space_len % 4 != 0:
            self._raise_message('layer 格式错误，空格长度：{}'.format(space_len))
        return (e + 1, space_len / 4)

    def __match_title(self, str, s):
        """匹配标题

        Args:
            str: 书签字符串
            s: 开始位置
        Returns:
            2 个元素的元组：(下一个位置，标题)
        """
        self.__check_str_index(str, s)

        e = BookmarkParser.__space_start_index(str, s)
        self.__check_str_index(str, e)
        return (e, str[s:e])

    def __match_first_space(self, str, s):
        """匹配第一个分隔符

        Args:
            str: 书签字符串
            s: 开始位置
        Returns:
            2 个元素的元组：(下一个位置，None)
        """
        self.__check_str_index(str, s)
        e = BookmarkParser.__space_end_index(str, s)
        self.__check_str_index(str, e)
        return (e + 1, None)

    def __match_page_no(self, str, s):
        """匹配页码

        Args:
            str: 书签字符串
            s: 开始位置
        Returns:
            2 个元素的元祖：(下一个位置，页码)
        """
        self.__check_str_index(str, s)
        page_no = str[s:len(str)]
        for c in page_no:
            if c < '0' or c > '9':
                self._raise_message('page no 不是数字')
        page_no = int(page_no)
        if page_no < 1:
            self._raise_message(
                'page no 错误，page no: {}'.format(page_no))
        return (len(str), page_no + self.__page_no_base)

    def __check_str_index(self, str, i):
        if i < 0 or i >= len(str):
            self._raise_message('格式错误')

    def _raise_message(self, message):
        """抛出与当前行号相关的异常

        Args:
            message: 异常信息
        Raises:
            RuntimeError
        """
        raise RuntimeError('line {}: {}'.format(self.__line_no, message))

    @staticmethod
    def __space_start_index(str, start):
        """从指定位置开始查找空格出现的第一个位置

        Args:
            str: 字符串
            start: 开始位置
        Returns:
            空格开始位置或 -1 如果没有空格
        """
        while start < len(str) and str[start] != ' ':
            start += 1
        if start < len(str) and str[start] == ' ':
            return start
        else:
            return -1

    @staticmethod
    def __space_end_index(str, start):
        """从指定位置开始查找空格结束的位置

        Args:
            str: 字符串
            start: 空格开始位置
        Returns:
            空格结束位置或 -1 如果没有空格
        """
        while start < len(str) and str[start] == ' ':
            start += 1
        return start - 1

    @staticmethod
    def __add_id_parent_id(bookmark_list):
        LOG.debug('开始建立元组 ID 关系')
        if bookmark_list is None or len(bookmark_list) == 0:
            return None
        bml = []
        id = 0
        # layer -> parent ID
        parent_id_dict = {}
        for bm in bookmark_list:
            id += 1
            (layer, title, page_no) = bm
            parent_id = None
            if layer > 0:
                parent_id = parent_id_dict[layer - 1]
            bm = (id, parent_id, layer, title, page_no)
            parent_id_dict[layer] = id
            bml.append(bm)
        return bml

    @staticmethod
    def __add_serial_no_to_title(bookmark_list):
        LOG.debug('开始设置书签章节标题')
        if bookmark_list is None or len(bookmark_list) == 0:
            return None
        bm_list = []
        serial_no_dict = {}
        for bm in bookmark_list:
            (id, parent_id, layer, title, page_no) = bm
            serial_no_dict = BookmarkParser.__incremental_serial_no(
                serial_no_dict, layer)
            title = BookmarkParser.__get_serial_no_string(
                serial_no_dict, layer) + ' ' + title
            bm_list.append((id, parent_id, layer, title, page_no))
        return bm_list

    @staticmethod
    def __incremental_serial_no(old_serial_no_dict, layer):
        serial_no_dict = {}
        for i in range(0, int(layer + 1)):
            if i in old_serial_no_dict:
                serial_no_dict[i] = old_serial_no_dict[i]
            else:
                serial_no_dict[i] = 0
        serial_no_dict[layer] += 1
        return serial_no_dict

    @staticmethod
    def __get_serial_no_string(serial_no_dict, layer):
        serial_no = ''
        for i in range(0, int(layer + 1)):
            if serial_no != '':
                serial_no += '.'
            serial_no += str(serial_no_dict[i])
        return serial_no


def __main_core():
    LOG.info('开始添加书签')
    try:
        parser = BookmarkParser('resources/bookmark.txt')
        bm_list = parser.parse()
    except Exception as e:
        LOG.error('解析书签错误：{}'.format(e))
        return

    LOG.info('开始读取 PDF 文件')
    try:
        with open('resources/input.pdf', 'rb') as i:
            input = PdfFileReader(i)
            LOG.debug('PDF 总页数：{}'.format(input.numPages))

            output = PdfFileWriter()
            LOG.info('开始复制 PDF 文件')
            for i in range(0, input.numPages):
                output.addPage(input.getPage(i))

            LOG.info('开始添加书签到 PDF 文件')
            # id -> bookmark object
            bm_dict = {}
            if bm_list is not None and len(bm_list) > 0:
                for bm in bm_list:
                    (id, parent_id, _, title, page_no) = bm
                    parent = None
                    if parent_id is not None:
                        parent = bm_dict[parent_id]
                    bookmark = output.addBookmark(title, page_no, parent)
                    LOG.debug(
                        '成功添加书签到 PDF 文件副本：{}，页码：{}'.format(title, page_no))
                    bm_dict[id] = bookmark

            LOG.info('开始写出 PDF 文件')
            __rebuild_dist_dir_and_output_pdf()
            with open('dist/output.pdf', 'wb') as o:
                output.write(o)
    except Exception as e:
        LOG.error('添加书签错误：{}'.format(e))


def __rebuild_dist_dir_and_output_pdf():
    dist = 'dist'
    if not os.path.exists(dist):
        os.mkdir(dist)
    if os.path.isfile(dist):
        os.remove(dist)
        os.mkdir(dist)

    output_pdf = dist + '/output.pdf'
    if os.path.exists(output_pdf):
        if os.path.isfile(output_pdf):
            os.remove(output_pdf)
        else:
            os.rmdir(output_pdf)


if __name__ == '__main__':
    __main_core()
