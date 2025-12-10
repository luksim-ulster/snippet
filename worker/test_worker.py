import unittest
from unittest.mock import patch, MagicMock
from worker import worker 

class TestWorkerLogic(unittest.TestCase):

    @patch('worker.requests.post')
    def test_call_azure_translator_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'translations': [{'text': 'Bonjour'}]}
        ]
        mock_post.return_value = mock_response

        result = worker.call_azure_translator("Hello", "fr")
        self.assertEqual(result, "Bonjour")
        
        args, _ = mock_post.call_args
        self.assertIn('/translate', args[0])

    @patch('worker.requests.post')
    def test_call_azure_translator_failure(self, mock_post):
        mock_post.side_effect = Exception("Network Down")
        result = worker.call_azure_translator("Hello", "fr")
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
