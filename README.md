# cloud_devops_IaC_project

Demonstrate Infrastructure as Code proficiency through this repository

### How to use this repo:

0) Be sure that you configured programmatic access to AWS using `aws configure`!

1) Create a config file that provides the following: 
    ```
    [Entry Name]
    name=STACK NAME
    template_path=FILE PATH TO CLOUDFORMATION TEMPLATE
    params_path=FILE PATH TO CLOUDFORMATION PARAMETER TEMPLATE
    capabilities=EXTRA PERMISSIONS FOR THE STACK (CAN LEAVE BLANK)
    depends_on=THE STACK'S DEPENDENCIES IN A CSV FORMAT
    ```
    If you are in doubt, follow the example ini file included in the repo.
    
2) To create the stacks:
    `python3 deploy_stacks.py`
    
3) To remove the stacks:
    `python3 remove_stacks.py`
    
Note that this repository does not generate one large stack; however, it creates several small stacks organized by 
service. 