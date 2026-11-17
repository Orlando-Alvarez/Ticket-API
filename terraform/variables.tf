variable "aws_region" {
  description = "AWS region where resources will be deploy"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ticket-api"
}

variable "environment" {
  description = "Deployment enviroment"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the Ticket-API VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR blocl for the public subnet"
  type        = string
  default     = "10.20.1.0/24"
}

variable "availability_zone" {
  description = "Availability zone for the public subnet"
  type        = string
  default     = "us-west-2a"
}

variable "private_subnet_cidr" {
  description = "CIDR block for the private subnet"
  type        = string
  default     = "10.20.2.0/24"
}

variable "instance_type" {
  description = "EC2 instance type for Ticker-API"
  type        = string
  default     = "t2.small"
}