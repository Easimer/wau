wau - WoW Addon Updater

wau keeps track of your World of Warcraft addons and updates them when a new
version is available.
You don't need neither a CurseForge account nor need to have the Twitch App
installed.

================================= Installation ================================

wau needs the following packages from pip to run:
- requests
- python-dateutil

=============================== Getting started ===============================

wau needs a manifest file to store some information about installed addons.
It's a simple text file called wau_manifest.txt and it must be placed in the
root of your AddOns directory.
Of course if you've never used this script before you won't have a manifest so
you need to create one first.

First line in a manifest file is a timestamp of when it was last updated; in a
newly created file this can be simply "-" (a single dash).
The rest of the file simply lists all the addons wau keeps track of. Each line
starts with an addon identifier and has the following format:

addon_id should_install_alpha_versions version

IDs can be found on the CurseForge page of an addon, on the right side of the
page; they're called "Project ID" there.
If you want to install alpha/beta versions of addons then specify a 1 in the
2nd column, otherwise leave it as a 0.
In a new file version fields should be left as "-", like the timestamp in the
first line.

Below is an example file; it will install the latest release of Details (2nd
line) and the latest beta release of Deadly Boss Mods (3rd line).

------------wau_manifest.txt------------
-
61284 0 -
3358 1 -
----------------------------------------

Place this file in your AddOns directory, e.g.:
D:/World of Warcraft/_retail_/Interface/AddOns/wau_manifest.txt
then run the script like this:
python wau.py D:/World of Warcraft/_retail_/Interface/AddOns/

After the first run the script will fill the omitted fields and the file will
look something like this:

------------wau_manifest.txt------------
2021-01-19T17:31:17.393Z
61284 0 DetailsRetail.9.0.2.8154.144(b)
3358 1 9.0.18-1-g0125762
----------------------------------------

wau won't touch addons that are not listed in the manifest.

On Windows you can create a shortcut to the script, so you won't have to open
a command line everytime you want to update your addons.
Pass -p in the arguments to pause the script after it's finished, so you can
look at it's output.

================================== Classic ====================================

The script should work on WoW Classic as well, you just need to pass
-g wow_classic
in the arguments to the script (it's untested, though).
