<?PHP
$json = file_get_contents('php://input');
header('content-type: text/html; charset: utf-8');
require "../web/library.php";

getDatabase();
ORM::configure('logging', true);
ORM::configure('driver_options', array(PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES utf8'));
$query = ORM::for_table('lifestream');

$scrobble_users = explode(',', lifestream_config('plex', 'scrobble_users'));
$slack_channel  = lifestream_config('plex', 'slack_channel');
$slack_botname  = lifestream_config('plex', 'slack_botname');

$action = json_decode($_POST['payload'], true);

// $log = date("r")."\n";
// $log .= print_r($action, 1)."\n-------\n";

if ($action['Metadata']['librarySectionType'] == 'artist') {
    exit;
}

$title = $action['Metadata']['title'];

if (isset($action['Metadata']['grandparentTitle'])) {
    if ($action['Metadata']['type'] == 'episode') {
        $title = sprintf("%s S%02dE%02d: %s", $action['Metadata']['grandparentTitle'], $action['Metadata']['parentIndex'], $action['Metadata']['index'], $title);
    } else {
        $title = $action['Metadata']['grandparentTitle'].': ';
    }
}

// $message = date("r")." ".$action['event']." by ".$action['Account']['title']." on ".$title;
// file_put_contents("/var/log/apache2/plex.log", $message."\n", FILE_APPEND | LOCK_EX);

switch ($action['event']) {
    case 'media.play':
        $message = $action['Account']['title']." Started watching ".$title;
        send_to_slack($message, $slack_botname, $slack_channel, ":tv:");
        break;

    case 'media.scrobble':
        $message = $action['Account']['title']." Finished watching ".$title;
        send_to_slack($message, $slack_botname, $slack_channel, ":tv:");


        if (in_array($action['Account']['title'], $scrobble_users)) {
            $message = "Watched ".$title;
            $guid = $action['Metadata']['guid'].date("Y-m");
            $icon = "https://art.istic.net/iconography/plex.png";
            addEntry("Media", $guid, $message, "Plex", date("Y-m-d"), false, $icon, $fulldata_json = $action);
        }
}




/*Array
(
    [event] => media.pause
    [user] => 1
    [owner] => 1
    [Account] => Array
        (
            [id] => 1
            [thumb] => https://plex.tv/users/72e157121c9458d7/avatar?c=1505143005
            [title] => Aquarion
        )

    [Server] => Array
        (
            [title] => Millpond
            [uuid] => a4dc8793dc9e06fc14132dc4c80fd5b1f7ece91d
        )

    [Player] => Array
        (
            [local] => 1
            [publicAddress] => 82.6.184.52
            [title] => Plex Web (Chrome)
            [uuid] => ko3sx9z35dchct0qfot2vvdc
        )

    [Metadata] => Array
        (
            [librarySectionType] => show
            [ratingKey] => 44331
            [key] => /library/metadata/44331
            [parentRatingKey] => 44328
            [grandparentRatingKey] => 44327
            [guid] => com.plexapp.agents.thetvdb://94571/3/3?lang=en
            [librarySectionID] => 4
            [librarySectionKey] => /library/sections/4
            [type] => episode
            [title] => Competitive Ecology
            [grandparentKey] => /library/metadata/44327
            [parentKey] => /library/metadata/44328
            [grandparentTitle] => Community
            [parentTitle] => Season 3
            [contentRating] => TV-PG
            [summary] => When the gang accepts a new person into the group, they learn how delicate their friendships really are.
            [index] => 3
            [parentIndex] => 3
            [rating] => 7.9
            [viewOffset] => 233000
            [lastViewedAt] => 1505146411
            [year] => 2011
            [thumb] => /library/metadata/44331/thumb/1504121738
            [art] => /library/metadata/44327/art/1504121757
            [parentThumb] => /library/metadata/44328/thumb/1504121742
            [grandparentThumb] => /library/metadata/44327/thumb/1504121757
            [grandparentArt] => /library/metadata/44327/art/1504121757
            [grandparentTheme] => /library/metadata/44327/theme/1504121757
            [originallyAvailableAt] => 2011-10-06
            [addedAt] => 1504118962
            [updatedAt] => 1504121738
            [Director] => Array
                (
                    [0] => Array
                        (
                            [id] => 5664
                            [filter] => director=5664
                            [tag] => Anthony Russo
                        )

                )

            [Writer] => Array
                (
                    [0] => Array
                        (
                            [id] => 4145
                            [filter] => writer=4145
                            [tag] => Maggie Bandur
                        )

                )

        )

)*/
