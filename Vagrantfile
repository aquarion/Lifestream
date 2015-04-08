# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
if not defined? VAGRANTFILE_API_VERSION
	VAGRANTFILE_API_VERSION = "2"
end

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
	config.vm.box = "ubuntu/trusty64"
	config.ssh.forward_agent = true

	config.vm.provision :ansible do |ansible|
	    ansible.playbook = "ansible/vagrant.yml"
	end

	config.vm.network :forwarded_port, host: 8000, guest: 8000
	config.vm.network :forwarded_port, host: 8443, guest: 8443
	
end
