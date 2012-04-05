-- MySQL dump 10.11
--
-- Host: localhost    Database: klind
-- ------------------------------------------------------
-- Server version	5.0.51a-24+lenny5-log

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `lifestream`
--

DROP TABLE IF EXISTS `lifestream`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `lifestream` (
  `id` int(11) default NULL,
  `type` varchar(15) collate utf8_unicode_ci NOT NULL default '',
  `systemid` varchar(128) collate utf8_unicode_ci NOT NULL default '',
  `title` varchar(2047) collate utf8_unicode_ci default NULL,
  `date_created` datetime default NULL,
  `image` varchar(255) collate utf8_unicode_ci NOT NULL default '',
  `url` varchar(511) collate utf8_unicode_ci NOT NULL,
  `source` varchar(255) collate utf8_unicode_ci NOT NULL default '',
  PRIMARY KEY  (`systemid`,`type`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `lifestream_locations`
--

DROP TABLE IF EXISTS `lifestream_locations`;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
CREATE TABLE `lifestream_locations` (
  `id` bigint(20) unsigned NOT NULL,
  `source` varchar(255) collate utf8_unicode_ci NOT NULL,
  `lat` double default NULL,
  `long` double default NULL,
  `lat_vague` double default NULL,
  `long_vague` double default NULL,
  `timestamp` datetime NOT NULL,
  `accuracy` int(11) NOT NULL,
  `title` varchar(255) collate utf8_unicode_ci default NULL,
  `icon` varchar(255) collate utf8_unicode_ci default NULL,
  PRIMARY KEY  (`id`,`source`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;
SET character_set_client = @saved_cs_client;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2012-04-05  1:05:32
