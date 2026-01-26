terraform {
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "0.7.6"
    }
  }
}

variable "libvirt_uri" {
  description = "URI of the libvirt daemon on the manager (e.g., qemu+ssh://manager_ip/system)"
  type        = string
  default     = "qemu:///system"  # Fallback to local if not specified
}

provider "libvirt" {
  uri = var.libvirt_uri
}

# Image Ubuntu de base (cached locally if possible)
resource "libvirt_volume" "ubuntu_base" {
  name   = "ubuntu-base.qcow2"
  pool   = "default"
  source = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  format = "qcow2"
}

%{~ for vm in vms ~}
# Disque pour VM: ${vm.name}
resource "libvirt_volume" "${vm.name}_disk" {
  name           = "${vm.name}.qcow2"
  pool           = "default"
  base_volume_id = libvirt_volume.ubuntu_base.id
  format         = "qcow2"
}

# Cloud-init pour VM: ${vm.name}
resource "libvirt_cloudinit_disk" "${vm.name}_init" {
  name = "cloudinit-${vm.name}.iso"
  pool = "default"

  user_data = templatefile(
    "${path.module}/cloud_init.cfg",
    {
      hostname    = "${vm.name}"
      user_name   = "${vm.name}"
      user_passwd = "${vm.ssh_password_hash}"
    }
  )
}

# VM: ${vm.name}
resource "libvirt_domain" "${vm.name}" {
  name   = "${vm.name}"
  memory = 512
  vcpu   = 1
  qemu_agent = true

  disk {
    volume_id = libvirt_volume.${vm.name}_disk.id
  }

  network_interface {
    network_name  = "default"
    wait_for_lease = true
  }

  cloudinit = libvirt_cloudinit_disk.${vm.name}_init.id

  depends_on = [libvirt_volume.ubuntu_base]
}

%{~ endfor ~}

# Output: informations de connexion pour chaque VM
%{~ for vm in vms ~}
output "${vm.name}_ip" {
  value       = libvirt_domain.${vm.name}.network_interface[0].addresses[0]
  description = "IP address of ${vm.name}"
}

%{~ endfor ~}
