terraform {
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "0.7.6"
    }
  }
}

variable "libvirt_uri" {
  description = "URI of the libvirt daemon on the manager (with SSH credentials)"
  type        = string
  default     = "qemu:///system"
}

provider "libvirt" {
  uri = var.libvirt_uri
}

# Image Ubuntu de base
resource "libvirt_volume" "ubuntu_base" {
  name   = "ubuntu-base.qcow2"
  pool   = "default"
  source = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  format = "qcow2"
}


# Disque pour VM: test
resource "libvirt_volume" "test_disk" {
  name           = "test.qcow2"
  pool           = "default"
  base_volume_id = libvirt_volume.ubuntu_base.id
  format         = "qcow2"
}

# Cloud-init pour VM: test
resource "libvirt_cloudinit_disk" "test_init" {
  name = "cloudinit-test-31200504.iso"
  pool = "default"

  user_data = templatefile(
    "${path.module}/cloud_init.cfg",
    {
      hostname    = "test"
            user_name   = "test"
      user_passwd = "$6$rounds=656000$Il4tOlca/BKHZX2s$fxSxJBxCa1de/c0OHufH7s6XgKO/OANbiE.X7DShxo50IDT3VMVXKogMjtu0f1vz4TCE1HnQ.xTCEkptkiIqE."
    }
  )
}

# VM: test
resource "libvirt_domain" "test" {
  name      = "test"
    memory    = 512
  vcpu      = 1
  machine   = "pc"
  arch      = "x86_64"
  type      = "qemu"
    qemu_agent  = true

  disk {
    volume_id = libvirt_volume.test_disk.id
  }

  network_interface {
    network_name  = "default"
    wait_for_lease = true
  }

  cloudinit = libvirt_cloudinit_disk.test_init.id

  depends_on = [libvirt_volume.ubuntu_base]
}

# Outputs: IP addresses for each VM

output "test_ip" {
  value       = libvirt_domain.test.network_interface[0].addresses[0]
  description = "IP address of test"
}
