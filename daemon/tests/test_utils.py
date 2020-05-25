import netaddr
import pytest

from core import utils
from core.errors import CoreError


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

    @pytest.mark.parametrize(
        "data,expected",
        [
            ("127", "127.0.0.0/32"),
            ("10.0.0.1/24", "10.0.0.1/24"),
            ("2001::", "2001::/128"),
            ("2001::/64", "2001::/64"),
        ],
    )
    def test_validate_ip(self, data: str, expected: str):
        value = utils.validate_ip(data)
        assert value == expected

    @pytest.mark.parametrize("data", ["256", "1270.0.0.1", "127.0.0.0.1"])
    def test_validate_ip_exception(self, data: str):
        with pytest.raises(CoreError):
            utils.validate_ip("")

    @pytest.mark.parametrize(
        "data,expected",
        [
            ("AA-AA-AA-FF-FF-FF", "aa:aa:aa:ff:ff:ff"),
            ("00:00:00:FF:FF:FF", "00:00:00:ff:ff:ff"),
        ],
    )
    def test_validate_mac(self, data: str, expected: str):
        value = utils.validate_mac(data)
        assert value == expected

    @pytest.mark.parametrize(
        "data", ["AAA:AA:AA:FF:FF:FF", "AA:AA:AA:FF:FF", "AA/AA/AA/FF/FF/FF"]
    )
    def test_validate_mac_exception(self, data: str):
        with pytest.raises(CoreError):
            utils.validate_mac(data)

    def test_random_mac(self):
        value = utils.random_mac()
        assert netaddr.EUI(value) is not None
