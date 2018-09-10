from core.misc import utils


class TestUtils:
    def test_make_tuple_fromstr(self):
        # given
        no_args = "()"
        one_arg = "('one',)"
        two_args = "('one', 'two')"
        unicode_args = u"('one', 'two', 'three')"

        # when
        no_args = utils.make_tuple_fromstr(no_args, str)
        one_arg = utils.make_tuple_fromstr(one_arg, str)
        two_args = utils.make_tuple_fromstr(two_args, str)
        unicode_args = utils.make_tuple_fromstr(unicode_args, str)

        # then
        assert no_args == ()
        assert len(one_arg) == 1
        assert len(two_args) == 2
        assert len(unicode_args) == 3
