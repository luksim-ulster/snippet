import unittest
from webapp import format_url, get_connection_settings

class TestWebappLogic(unittest.TestCase):

    def test_format_url_simple(self):
        base_url = "https://example.com/api/items/%7Bid%7D"
        item_id = "123"
        expected = "https://example.com/api/items/123"
        
        result = format_url(base_url, item_id)
        self.assertEqual(result, expected)

    def test_format_url_special_chars(self):
        base_url = "https://example.com/api/items/%7Bid%7D"
        item_id = "test/123"
        expected = "https://example.com/api/items/test%2F123"
        
        result = format_url(base_url, item_id)
        self.assertEqual(result, expected)

    def test_get_connection_settings(self):
        connection_string = "DefaultEndpointsProtocol=https;AccountName=testaccountname;AccountKey=testaccountkey==;EndpointSuffix=core.windows.net"
        
        account_name, account_key = get_connection_settings(connection_string)
        
        self.assertEqual(account_name, "testaccountname")
        self.assertEqual(account_key, "testaccountkey==")

if __name__ == '__main__':
    unittest.main()
