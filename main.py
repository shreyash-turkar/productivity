#! /Users/Shreyash.Turkar/workspace/sdmain/polaris/.buildenv/bin/python

# turkarshreyash@gmail.com * Copyright 2023
# Isendgard runner. Reloads Isendgard module 
# if reload exception is raised.


import sys
from importlib import reload

import ProjectIsengard

cache_file = '/Users/Shreyash.Turkar/Documents/.isengard_cache'

if __name__ == '__main__':
    line_before_reload = None
    while True:
        isengard = ProjectIsengard.IsengardShell(cache_file)
        print(line_before_reload)
        if line_before_reload:
            isengard.preloop()
            isengard.onecmd(line_before_reload)
        try:
            isengard.cmdloop()
        except ProjectIsengard.ReloadException as e:
            isengard.postloop()
            line_before_reload = str(e)
            reload(ProjectIsengard)
            continue
        except Exception:
            isengard.postloop()
            raise
        sys.exit(0)
