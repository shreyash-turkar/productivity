eval "$(/opt/homebrew/bin/brew shellenv)"
eval "$(pyenv init --path)"

# Folders
export WORKSPACE_PATH='~/workspace'
export SDMAIN="$WORKSPACE_PATH/sdmain"
export JAVA_HOME="/usr/bin/java"

alias sd_dev_box="$SDMAIN/lab/sd_dev_box/sd_dev_box"
export EDITOR=vim

# Exports
export PATH="$PATH:/usr/local/bin/"
export PATH="$PATH:/somewhere/arcanist/bin/"
export PATH="$PATH:/Users/Shreyash.Turkar/.yarn/bin/"

# Bodega Alias
alias bodega=$SDMAIN/lab/bin/bodega
alias orders='bodega list orders'
alias consume='bodega consume order'

close_order ()
{
    bodega close order $@
}


# Bodega Orders
order_cdm ()
{
    bodega place order 'cdm:cdm_cluster()' -t max -ctx {"CDM $(date '+%d %B %A')"}
}

order_cdm_artifacts ()
{
    bodega place order "cdm:cdm_cluster(artifacts_url=$1)" -t max -ctx {"CDM-artifacts $(date '+%d %B %A')"}
}

order_cdm_version ()
{
    bodega place order "cdm:cdm_cluster(version=$1)" -t max -ctx {"CDM-$1 $(date '+%d %B %A')"}
}

order_cdm_version_3node ()
{
    bodega place order "cdm:cdm_cluster(version=$1, node_count=3)" -t max -ctx {"3 node CDM $(date '+%d %B %A')"}
}

order_hyperv ()
{
    bodega place order 'hyerpv:vm_machine(location=COLO,image_source=hyperv_2016_vm_template)' -ctx {"Hyperv $(date '+%d %B %A')"} -t max
}

order_linux_host ()
{
    bodega place order 'vm:vm_machine(location=colo,image_source=ubuntu_16_04_lts, network=native)' -ctx {"Linux Host $(date '+%d %B %A')"} -t max --no_wait
}

order_polaris ()
{
    bodega place order 'cookbook_item(recipe=polaris-deployment)' -ctx {"Polaris $(date '+%d %B %A')"} -t max
}

order_scvmm ()
{
    bodega place order 'scvmm:vm_machine(drs=True, image_source=hyperv_scvmm_2016_template, location=COLO, network=native)' -ctx {"SCVMM $(date '+%d %B %A')"} -t max
}

order_windows_host ()
{
    bodega place order 'vm:vm_machine(location=colo,image_source=legacy-windowshost-2016, network=native)' -ctx {"Windows Host$(date '+%d %B %A')"} -t max --no_wait
}

order_active_directory ()
{
    bodega place order 'cookbook_item(recipe=active-directory, domain_template=windows2019, dc_count=1, override_domain_name=true, location=COLO)'  -ctx  {"Active Directory $(date '+%d %B %A')"} -t max --no_wait
}

order_active_directory_3_hosts ()
{
    bodega place order 'cookbook_item(recipe=active-directory, domain_template=windows2019, dc_count=3, override_domain_name=true, location=COLO)'  -ctx  {"Active Directory $(date '+%d %B %A')"} -t max --no_wait
}


# Bodega Functions
details() {
	consume $1 | grep -e 'ipv4' -e 'item_type'
}

provision_polaris ()
{
    account='temp02' \
    &&
    echo "Running sp-account-create -a $account -d $@" \
    &&
    sp-account-create -a $account -d $@ \
    &&
    echo "Running: sp-user-create -a $account -u admin -p b8bkPrhVVxyY7Jg -d $@" \
    &&
    sp-user-create -a $account -u shreyash.turkar@rubrik.com -p admin -d $@ \
    &&
    echo "sp-account-ui -a $account -d $@" \
    &&
    sp-account-ui -a $account -d $@ \
    &&
    sp-account-tag add -d $@ -t ActiveDirectoryEnabled \
                                RDPCustomer \
                                UiActiveDirectoryEnabled \
                                FilesetInventory \
                                # HypervEnabled \
                                # HyperVHierarchyEnabled \
                                # HyperVInventoryViewEnabled \
                                GlobalSLAForCDMSnappablesEnabled \
                                RBACForGlobalSLA \
                                NasFeatureEnablement \
                                NasInventoryEnabled \
                                NasInventoryGAEnabled \
                                NutanixEnabled \
                                TprEnabled \
                    -a $account
}

extend_order ()
{
    bodega extend order $@ -t max
}

extend_all_orders ()
{
	bodega extend order $(orders | awk '{print $1}' | tail -n +3) -t max
}

alias activate_po="source ./polaris/.buildenv/bin/activate"

alias activate_re="source ./tools/env/dev activate"

register_cdm_to_polaris () {
	TOKEN=`sp-account-token-generate -d $1 -a $2 -u shreyash.turkar@rubrik.com`
	sp-sdmain-register -s $3 -t $TOKEN -u admin -p RubrikAdminPassword	
}

# Cluster Alias
alias cluster="$SDMAIN/deployment/cluster.sh"

cssh () {
    ssh -i ./deployment/ssh_keys/ubuntu.pem ubuntu@$@
}

# VNC Alias
alias vnc_2560x1440="vncserver -geometry 2540x1440"
alias vnc_2304x1296="vncserver -geometry 2304x1296"
alias vnc_2048x1152="vncserver -geometry 2048x1152"
alias vnc_1920x1080="vncserver -geometry 1920x1080"
alias vnc_1440x900="vncserver -geometry 1440x900"
alias vnc_kill="vncserver -kill :1"

# Pycharm
export pycharm="/home/ubuntu/Documents/Apps/pycharm-community-2022.3.2/bin/pycharm.sh"


ffconvert() {
  ffmpeg -i $1 -c copy -movflags +faststart $2.mp4
}

gls ()
{
    git show --name-only | cat;
    echo -e '\n\n---------------CHANGED FILES---------------------------\n';
    git status -s;
    echo -e '\n'
}

export rklog=$SDMAIN/tools/logging/rklog.py