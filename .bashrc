eval "$(/opt/homebrew/bin/brew shellenv)"
eval "$(pyenv init --path)"

# Folders
export WORKSPACE_PATH='~/workspace'
export SDMAIN="$WORKSPACE_PATH/sdmain"

alias sd_dev_box="$SDMAIN/lab/sd_dev_box/sd_dev_box"

# Exports
export PATH="$PATH:/usr/local/bin/"
export PATH="$PATH:/usr/local/bin/code"
export PATH="$PATH:/somewhere/arcanist/bin/"
export PATH="$PATH:/Users/Shreyash.Turkar/.yarn/bin/"

# Bodega Alias
alias bodega=$SDMAIN/lab/bin/bodega
alias orders='bodega list orders'
alias consume='bodega consume order'

# Bodega Functions
details() {
	consume $1 | grep -e 'ipv4' -e 'item_type'
}

# Cluster Alias
alias cluster="$SDMAIN/deployment/cluster.sh"

# VNC Alias
alias vnc_2560x1440="vncserver -geometry 2540x1440"
alias vnc_2304x1296="vncserver -geometry 2304x1296"
alias vnc_2048x1152="vncserver -geometry 2048x1152"
alias vnc_1920x1080="vncserver -geometry 1920x1080"
alias vnc_1440x900="vncserver -geometry 1440x900"
alias vnc_kill="vncserver -kill :1"

# Pycharm
export pycharm="/home/ubuntu/Documents/Apps/pycharm-community-2022.3.2/bin/pycharm.sh"
