import json
import os
import subprocess
import unittest
from unittest.mock import patch
import accounts


class AccountTests(unittest.TestCase):
    def test_environment_excludes_api_credentials(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'secret','ANTHROPIC_AUTH_TOKEN':'secret'}):
            env=accounts.environment()
        self.assertNotIn('OPENAI_API_KEY',env)
        self.assertNotIn('ANTHROPIC_AUTH_TOKEN',env)

    def test_unconnected_account_cannot_generate(self):
        with patch.object(accounts,'status',return_value={'connected':False}),patch.object(accounts,'run') as run:
            with self.assertRaises(ValueError):accounts.generate('account:claude','',[],100)
            run.assert_not_called()

    def test_codex_receives_context_on_stdin_with_tools_disabled(self):
        output=json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'Réponse'}})
        with patch.object(accounts,'status',return_value={'connected':True}),patch.object(accounts,'executable',return_value='codex.exe'),patch.object(accounts,'run',return_value=subprocess.CompletedProcess([],0,output,'')) as run:
            self.assertEqual(accounts.generate('account:chatgpt','tuteur',[{'role':'user','content':'cours confidentiel'}]),'Réponse')
        args=run.call_args.args[0]
        self.assertIn('--ignore-user-config',args)
        self.assertIn('read-only',args)
        self.assertIn('shell_tool',args)
        self.assertNotIn('cours confidentiel',' '.join(args))
        self.assertIn('cours confidentiel',run.call_args.kwargs['input'])

    def test_claude_disables_tools_and_extracts_json(self):
        output=json.dumps({'result':'```json\n{"ok":true}\n```','is_error':False})
        with patch.object(accounts,'status',return_value={'connected':True}),patch.object(accounts,'executable',return_value='claude.exe'),patch.object(accounts,'run',return_value=subprocess.CompletedProcess([],0,output,'')) as run:
            result=accounts.generate('account:claude','',[],format={'type':'object'})
        self.assertTrue(json.loads(result)['ok'])
        args=run.call_args.args[0]
        self.assertEqual(args[args.index('--tools')+1],'')
        self.assertIn('--safe-mode',args)
        self.assertIn('--strict-mcp-config',args)

    def test_provider_failure_not_returned_as_success(self):
        with patch.object(accounts,'status',return_value={'connected':True}),patch.object(accounts,'executable',return_value='codex.exe'),patch.object(accounts,'run',return_value=subprocess.CompletedProcess([],1,'','private error')):
            with self.assertRaises(ValueError) as error:accounts.generate('account:chatgpt','',[])
        self.assertNotIn('private',str(error.exception))
