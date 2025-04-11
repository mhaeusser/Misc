1st Prompt to deepseek: Can you write a script that recursively clones all git repos when I only know the URL and the group id?
2nd Prompt to deepseek: Can you add a command line switch so I can use the script also for updating my local repos?

Invocation:
python gitlab_group_cloner.py URL GROUP_ID --output-dir ./repos --private-token <PRIVATE_TOKEN> [--update]
