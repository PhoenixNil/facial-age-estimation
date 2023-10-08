import os

import torch
from torch import nn as nn
from torch.nn import Linear, functional as F, Dropout
import torchvision.models as models
from torchvision.models import resnet50


class FeatureExtractionResnext101(nn.Module):
        def __init__(self):
            super(FeatureExtractionResnext101, self).__init__()

            self.base_net = models.resnext101_32x8d(pretrained=True)

        def forward(self, input):
            x = self.base_net.conv1(input)
            x = self.base_net.bn1(x)
            x = self.base_net.relu(x)
            x = self.base_net.maxpool(x)

            x = self.base_net.layer1(x)
            x = self.base_net.layer2(x)
            x = self.base_net.layer3(x)
            x = self.base_net.layer4(x)

            x = self.base_net.avgpool(x)
            x = torch.flatten(x, 1)

            return x
        

class FeatureExtractionResnet50(nn.Module):
        def __init__(self):
            super(FeatureExtractionResnet50, self).__init__()

            self.base_net = models.resnet50(pretrained=True)

        def forward(self, input):
            x = self.base_net.conv1(input)
            x = self.base_net.bn1(x)
            x = self.base_net.relu(x)
            x = self.base_net.maxpool(x)

            x = self.base_net.layer1(x)
            x = self.base_net.layer2(x)
            x = self.base_net.layer3(x)
            x = self.base_net.layer4(x)

            x = self.base_net.avgpool(x)
            x = torch.flatten(x, 1)

            return x



class UnifiedClassificaionAndRegressionAgeModel(nn.Module):
        def __init__(self, num_classes, age_interval, min_age, max_age, device=torch.device("cuda:0")):
            super(UnifiedClassificaionAndRegressionAgeModel, self).__init__()
            self.device = device
            self.age_intareval = age_interval
            self.min_age = min_age
            self.max_age = max_age
            self.labels = range(num_classes)

            # self.base_net = FeatureExtractionResnext101()
            self.base_net = FeatureExtractionResnet50()
            k = 2048
            self.num_features = 2048


            self.fc_first_stage = Linear(self.num_features, k)
            self.class_head = Linear(k, num_classes)

            self.fc_second_stage = Linear(self.num_features, k)

            self.regression_heads = []
            # self.classification_heads = []
            self.centers = []
            for i in self.labels:
                self.regression_heads.append(Linear(k, 1))
                # self.classification_heads.append(Linear(k, int(self.age_intareval*2)))
                center = min_age + 0.5 * age_interval + i * age_interval
                self.centers.append(center)

            self.regression_heads = nn.ModuleList(self.regression_heads)
            # self.classification_heads = nn.ModuleList(self.classification_heads)

        def freeze_base_cnn(self, should_freeze=True):
            for param in self.base_net.parameters():
                param.requires_grad = not should_freeze

        def forward(self, input_images, p=0.5):

            base_embedding = self.base_net(input_images)
            base_embedding = F.leaky_relu(base_embedding)
            # base_embedding = Dropout(p)(base_embedding)

            # first stage
            class_embed = self.fc_first_stage(base_embedding)
            class_embed = F.normalize(class_embed, dim=1, p=2)
            x = F.leaky_relu(class_embed)
            x = Dropout(p)(x)

            classification_logits = self.class_head(x)

            weights = nn.Softmax()(classification_logits)

            # second stage
            x = self.fc_second_stage(base_embedding)
            x = F.leaky_relu(x)
            x = Dropout(p)(x)

            t = []
            for i in self.labels:
                # t.append(torch.squeeze(self.regression_heads[i](x)) * weights[:, i])
                t.append(torch.squeeze(self.regression_heads[i](
                    x) + self.centers[i]) * weights[:, i])
                # _, local_res = torch.max(self.classification_heads[i](x), 1)
                # t.append(torch.squeeze(local_res - int(self.age_intareval*2) / 2 + self.centers[i]) * weights[:, i])

            age_pred = torch.stack(t, dim=0).sum(
                dim=0) / torch.sum(weights, dim=1)

            return classification_logits, age_pred